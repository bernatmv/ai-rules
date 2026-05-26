"""Individual PRD validation checks with registry pattern."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Union

from prd.shared import WHEN_THEN_RE, NFR_CATEGORIES
from sdd_core.matchers import WordMatcher

THEN_SUBJECT_RE = re.compile(
    r"THEN\s+(?:\[?\w[\w\s\-]*\]?)\s+SHALL\b", re.IGNORECASE
)

PLACEHOLDER_PATTERNS = [
    re.compile(r"^\[.*\]$"),
    re.compile(r"^\[Specific values"),
    re.compile(r"^\[Uptime target"),
    re.compile(r"^\[Current vs"),
    re.compile(r"^\[Auth requirements"),
    re.compile(r"^\[Consistency model"),
    re.compile(r"^\[Logging,"),
]

_FR_HEADING_PHRASES = WordMatcher(("Functional Requirements",), case_sensitive=True)
FR_HEADING_RE = _FR_HEADING_PHRASES.compose(
    prefix=r"^#{1,3}\s+.*",
    extra_alternatives=(r"FR-\d",),
)
FR_SUB_HEADING_RE = re.compile(r"^#{1,4}\s+FR-")
HEADING_RE = re.compile(r"^#{1,3}\s+")


def is_placeholder(text: str) -> bool:
    """Check if text contains only template placeholder content."""
    stripped = text.strip()
    if not stripped:
        return True
    for pat in PLACEHOLDER_PATTERNS:
        if pat.match(stripped):
            return True
    return False


def check_when_then(content: str) -> list[str]:
    """Check WHEN/THEN format in requirements sections."""
    issues: list[str] = []
    in_requirements = False
    req_count = 0
    when_then_count = 0

    for line in content.splitlines():
        stripped = line.strip()
        if FR_HEADING_RE.match(stripped):
            in_requirements = True
            continue
        if HEADING_RE.match(stripped) and in_requirements:
            if not FR_SUB_HEADING_RE.match(stripped):
                in_requirements = False
                continue

        if in_requirements and stripped.startswith("|") and "WHEN" not in stripped.upper():
            cells = [c.strip() for c in stripped.split("|")[1:-1]]
            if len(cells) >= 2 and cells[-1] and not cells[-1].startswith("-"):
                req_text = cells[-1]
                if req_text and not req_text.startswith("Requirement"):
                    req_count += 1

        if in_requirements and WHEN_THEN_RE.search(stripped):
            when_then_count += 1
            if not THEN_SUBJECT_RE.search(stripped):
                issues.append(f"THEN clause missing named subject: {stripped[:80]}")

    if when_then_count == 0:
        has_fr_section = (in_requirements or req_count > 0 or any(
            re.search(r"Functional Requirements", line) for line in content.splitlines()
            if line.strip().startswith("#")
        ))
        if has_fr_section:
            issues.append("No WHEN/THEN patterns found in requirements section")

    return issues


def check_nfr_categories(sections: dict[str, str]) -> list[str]:
    """Verify all 6 NFR categories present and non-placeholder."""
    issues: list[str] = []
    nfr_section: str | None = None
    for key in sections:
        if "non-functional" in key.lower() or key.lower() == "6b":
            nfr_section = sections[key]
            break

    if nfr_section is None:
        nfr_content = ""
        for key, val in sections.items():
            if any(cat.lower() in key.lower() for cat in NFR_CATEGORIES):
                nfr_content += val
        if not nfr_content:
            issues.append("Non-Functional Requirements section not found")
            return issues
        nfr_section = nfr_content

    for category in NFR_CATEGORIES:
        found = False
        for key in sections:
            if category.lower() in key.lower():
                found = True
                section_text = sections[key].strip()
                if is_placeholder(section_text):
                    issues.append(f"NFR category '{category}' contains only placeholder text")
                break
        if not found and category.lower() not in nfr_section.lower():
            issues.append(f"NFR category '{category}' not found")

    return issues


def _find_section_table(
    content: str, section_name: str,
) -> tuple[bool, list[str], list[list[str]]]:
    """Find a section's table: returns (section_found, header_cells, data_rows).

    Shared parser for both column-checking and row-extraction use cases.
    """
    in_section = False
    found_section = False
    found_header = False
    header_cells: list[str] = []
    data_rows: list[list[str]] = []

    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") and section_name.lower() in stripped.lower():
            in_section = True
            found_section = True
            continue
        if stripped.startswith("#") and in_section and section_name.lower() not in stripped.lower():
            break
        if not in_section or not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.split("|")[1:-1]]
        if not found_header:
            found_header = True
            header_cells = cells
            continue
        if all(c.replace("-", "").replace(" ", "") == "" for c in cells):
            continue
        data_rows.append(cells)

    return found_section, header_cells, data_rows


def check_table_columns(content: str, section_name: str, required_columns: list[str]) -> list[str]:
    """Check that a table in the specified section has required column headers."""
    found_section, header_cells, _ = _find_section_table(content, section_name)

    if not found_section:
        return [f"'{section_name}' section not found"]
    if not header_cells:
        return [f"'{section_name}' section has no table"]

    lower_headers = [c.lower() for c in header_cells]
    issues: list[str] = []
    for col in required_columns:
        if not any(col.lower() in cell for cell in lower_headers):
            issues.append(f"'{section_name}' table missing column: {col}")
    return issues


def check_open_questions(content: str) -> list[str]:
    """Check open questions have Owner + Due Date + Blocks columns."""
    return check_table_columns(content, "Open Questions", ["Owner", "Due Date", "Blocks"])


def check_alternatives(sections: dict[str, str]) -> list[str]:
    """Check Alternatives Considered section is non-empty."""
    issues: list[str] = []
    for key, val in sections.items():
        if "alternatives" in key.lower() and "considered" in key.lower():
            non_empty_lines = [
                line for line in val.strip().splitlines()
                if line.strip() and not line.strip().startswith("|--") and line.strip() != "|"
            ]
            table_data = [
                line for line in non_empty_lines
                if line.strip().startswith("|") and not all(c in "|- " for c in line.strip())
            ]
            header_only = all(
                any(c.strip() in ("Alternative", "Evaluated", "Ruled Out Because", "")
                    for c in line.split("|")[1:-1])
                for line in table_data
            ) if table_data else True
            if not non_empty_lines or (len(table_data) <= 1 and header_only):
                issues.append("Alternatives Considered section is empty or has no entries")
            return issues
    issues.append("Alternatives Considered section not found")
    return issues


def _cell_is_tbd(cell: str) -> bool:
    """Return True if a cell value is effectively TBD/placeholder."""
    stripped = cell.strip().lower()
    return stripped in ("tbd", "t.b.d.", "t.b.d", "to be determined", "n/a", "")


def check_rollout_plan(content: str) -> list[str]:
    """Check rollout plan has Success Gate + Rollback Plan columns and non-TBD content."""
    found_section, header_cells, rows = _find_section_table(content, "Phased Rollout")
    required_columns = ["Success Gate", "Rollback Plan"]

    if not found_section:
        return [f"'Phased Rollout' section not found"]
    if not header_cells:
        return [f"'Phased Rollout' section has no table"]

    lower_headers = [c.lower() for c in header_cells]
    issues: list[str] = []
    for col in required_columns:
        if not any(col.lower() in cell for cell in lower_headers):
            issues.append(f"'Phased Rollout' table missing column: {col}")
    if issues:
        return issues

    if rows and all(all(_cell_is_tbd(c) for c in row) for row in rows):
        issues.append("Rollout plan has only TBD/placeholder content — needs substantive gates")
    return issues


def check_goals_table(content: str) -> list[str]:
    """Check goals table has Metric + Target + Measurement Method columns."""
    return check_table_columns(content, "Goals", ["Metric", "Target", "Measurement Method"])


def check_nongoals_reason(content: str) -> list[str]:
    """Check non-goals table has a Reason column."""
    return check_table_columns(content, "Non-Goals", ["Reason"])


@dataclass
class Check:
    id: str
    func: Callable[[Union[str, dict]], list[str]]
    input_type: str  # "content" or "sections"
    tier: int = 1
    description: str = ""
    section: str = ""
    gate: str = ""  # "pre-requirements" | "pre-generation" | "" (both)


CHECK_REGISTRY: list[Check] = [
    Check(
        "requirements_when_then_format", check_when_then, "content",
        tier=1, description="WHEN/THEN format present in requirement entries",
        section="6. Functional Requirements", gate="pre-generation",
    ),
    Check(
        "nfrs_all_categories_specific", check_nfr_categories, "sections",
        tier=1, description="All 6 NFR categories present and non-placeholder",
        section="6b. Non-Functional Requirements", gate="pre-generation",
    ),
    Check(
        "open_questions_have_owners", check_open_questions, "content",
        tier=1, description="Open questions have Owner + Due Date + Blocks columns",
        section="9. Open Questions", gate="pre-generation",
    ),
    Check(
        "alternatives_considered_present", check_alternatives, "sections",
        tier=1, description="Alternatives Considered section non-empty",
        section="7. Alternatives Considered",
    ),
    Check(
        "rollout_plan_with_gates", check_rollout_plan, "content",
        tier=1, description="Rollout plan has Success Gate + Rollback Plan columns",
        section="8. Phased Rollout",
    ),
    Check(
        "goals_table_complete", check_goals_table, "content",
        tier=1, description="Goals table has Metric + Target + Measurement Method columns",
        section="3. Goals", gate="pre-requirements",
    ),
]
