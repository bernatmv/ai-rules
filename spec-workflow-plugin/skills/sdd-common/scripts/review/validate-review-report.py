#!/usr/bin/env python3
"""Validate a code review report for structural completeness.

Checks that the report includes all required dimensions, principles,
and anti-pattern evaluations.  Outputs structured JSON and exits 0
(valid) or 1 (invalid) to enable feedback-loop integration.

Usage:
    validate-review-report.py --report <path-to-report.md>
    validate-review-report.py --report -            # read from stdin
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import argparse
import re
import sys

from sdd_core import cli, output
from review.review_config import (
    DIMENSION_DISPLAYS as REQUIRED_DIMENSIONS,
    PRINCIPLES as REQUIRED_PRINCIPLES,
    ANTI_PATTERNS as REQUIRED_ANTI_PATTERNS,
)
from sdd_core.validation_helpers import format_error_list
from review_quality.constants import (
    MIN_REPORT_COLUMNS, REPORT_SCORE_COL, REPORT_EVIDENCE_COL,
)

_PLACEHOLDER_RE = re.compile(r"^\{.*\}$")
_SCORE_RE = re.compile(r"\d+\s*/\s*5")

_COL_SCORE = REPORT_SCORE_COL
_COL_EVIDENCE = REPORT_EVIDENCE_COL
_MIN_COLUMNS = MIN_REPORT_COLUMNS


def _normalize(text: str) -> str:
    return text.strip().lower()


def _parse_table_rows(text: str, header_marker: str) -> list[list[str]]:
    """Extract table rows from the first markdown table after *header_marker*."""
    lines = text.split("\n")
    in_section = False
    rows: list[list[str]] = []
    header_seen = False
    for line in lines:
        stripped = line.strip()
        if header_marker.lower() in stripped.lower():
            in_section = True
            header_seen = False
            continue
        if in_section:
            if stripped.startswith("|"):
                if not header_seen:
                    header_seen = True
                    continue
                if set(stripped.replace("|", "").strip()) <= {"-", ":", " "}:
                    continue
                cells = [c.strip() for c in stripped.split("|")[1:-1]]
                rows.append(cells)
            elif header_seen and rows:
                break
    return rows


def _validate_checklist_section(
    rows: list[list[str]],
    expected_items: list[str],
    *,
    substring_match: bool = False,
    score_check=None,
    evidence_check: bool = False,
) -> tuple[list[str], list[str], list[str]]:
    """Validate a checklist section from a report table.

    Returns (missing, score_errors, evidence_errors).
    """
    found_items = {_normalize(row[0]) for row in rows if row}
    missing: list[str] = []
    score_errors: list[str] = []
    evidence_errors: list[str] = []

    for item in expected_items:
        norm = _normalize(item)
        if norm not in found_items:
            if substring_match and any(norm in fap for fap in found_items):
                pass  # substring hit counts as found
            else:
                missing.append(item)
                continue

        matching = [r for r in rows if _normalize(r[0]) == norm]
        if not matching and substring_match:
            matching = [r for r in rows if norm in _normalize(r[0])]
        if not matching:
            continue
        row = matching[0]

        if score_check and len(row) > _COL_SCORE:
            if not score_check(row[_COL_SCORE]):
                score_errors.append(f"{item}: score column missing numeric X/5 value")

        if evidence_check and len(row) >= _MIN_COLUMNS:
            evidence = row[_COL_EVIDENCE].strip()
            if not evidence or _PLACEHOLDER_RE.match(evidence):
                evidence_errors.append(item)

    return missing, score_errors, evidence_errors


def validate_report(text: str) -> dict:
    """Validate report text.  Returns a result dict with ``valid`` bool."""
    dim_rows = _parse_table_rows(text, "Dimension Scorecards")
    missing_dimensions, dimension_score_errors, _ = _validate_checklist_section(
        dim_rows, REQUIRED_DIMENSIONS,
        score_check=lambda s: _SCORE_RE.search(s),
    )

    princ_rows = _parse_table_rows(text, "Principle Scorecard")
    missing_principles, _, empty_evidence = _validate_checklist_section(
        princ_rows, REQUIRED_PRINCIPLES,
        evidence_check=True,
    )

    ap_rows = _parse_table_rows(text, "Anti-Pattern Checks")
    missing_anti_patterns, _, _ = _validate_checklist_section(
        ap_rows, REQUIRED_ANTI_PATTERNS,
        substring_match=True,
    )

    valid = (
        not missing_dimensions
        and not missing_principles
        and not missing_anti_patterns
        and not empty_evidence
        and not dimension_score_errors
    )

    return {
        "valid": valid,
        "missing_dimensions": missing_dimensions,
        "missing_principles": missing_principles,
        "missing_anti_patterns": missing_anti_patterns,
        "empty_evidence": empty_evidence,
        "dimension_score_errors": dimension_score_errors,
    }


def main() -> None:
    parser = cli.strict_parser(
        description="Validate a code review report for structural completeness",
    )
    parser.add_argument(
        "--report",
        required=True,
        help=(
            "Path to the report markdown file (use '-' for stdin). "
            "Convention: standalone → docs/code-review-{scope}-{date}.md, "
            "spec-aware → .spec-workflow/specs/{name}/code-review-{date}.md"
        ),
    )
    args = parser.parse_args()

    if args.report == "-":
        text = sys.stdin.read()
    else:
        try:
            with open(args.report) as f:
                text = f.read()
        except FileNotFoundError:
            output.error(
                f"Report file not found: {args.report}",
                hint="Generate the report in Step 6 before running validation",
            )
        except OSError as exc:
            output.error(
                f"Cannot read report file: {exc}",
                hint="Check file permissions and path",
            )

    result = validate_report(text)

    if result["valid"]:
        output.success(result, "Report structure is valid")

    errors: list[str] = []
    if result["missing_dimensions"]:
        errors.append(f"Missing dimensions: {', '.join(result['missing_dimensions'])}")
    if result["missing_principles"]:
        errors.append(f"Missing principles: {', '.join(result['missing_principles'])}")
    if result["missing_anti_patterns"]:
        errors.append(f"Missing anti-patterns: {', '.join(result['missing_anti_patterns'])}")
    if result["empty_evidence"]:
        errors.append(f"Empty evidence for: {', '.join(result['empty_evidence'])}")
    if result["dimension_score_errors"]:
        errors.append(f"Score errors: {format_error_list(result['dimension_score_errors'])}")

    output.result(result, format_error_list(errors), exit_code=1)


if __name__ == "__main__":
    cli.run_main(main)
