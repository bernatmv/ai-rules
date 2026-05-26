"""Requirements ↔ tasks traceability extraction (pure functions).

Single source of truth for the regex / heuristic logic the
``spec/check-traceability.py`` shim consumes. Keeps the shim itself a
thin argparse + envelope wrapper.
"""
from __future__ import annotations

import re
from typing import TypedDict

from .matchers import WordMatcher
from .tasks import METADATA_RE as _METADATA_RE, TASK_LINE_RE as _TASK_LINE_RE

__all__ = [
    "TraceabilityResult",
    "extract_requirement_ids",
    "extract_task_requirement_refs",
    "analyse_traceability",
    "parent_id",
    "is_bug_fix_content",
]


_HEADING_RE = re.compile(r"^#{1,4}\s+.*?(\d+(?:\.\d+)*)")
_REQ_REF_RE = re.compile(r"_Requirements:\s*([^_]*)_")
_REQ_ID_RE = re.compile(r"\d+(?:\.\d+)*")
_BUG_FIX_HEADING_PHRASES = WordMatcher(
    ("Bug Summary", "Current Behavior", "Expected Behavior"),
    case_sensitive=True,
)
_BUG_FIX_HEADING_RE = _BUG_FIX_HEADING_PHRASES.compose(prefix=r"^##\s+")


class TraceabilityResult(TypedDict):
    """Outcome of comparing requirement IDs to task references."""

    result: str
    covered: list[str]
    missing: list[str]
    validRefs: list[str]
    orphanRefs: list[str]


def parent_id(ref: str) -> str:
    """Return the top-level requirement id (``"1.2.3"`` → ``"1"``)."""
    return ref.split(".")[0]


def extract_requirement_ids(content: str) -> list[str]:
    """Extract numbered requirement ids from headings in *content*."""
    ids: list[str] = []
    for line in content.splitlines():
        match = _HEADING_RE.match(line.strip())
        if match:
            ids.append(match.group(1))
    return ids


def extract_task_requirement_refs(content: str) -> list[str]:
    """Extract ``_Requirements:`` references from a tasks.md *content*.

    Skips refs nested inside ``_Prompt:`` blocks so the lifecycle
    suffix's example refs do not bleed into the traceability check.
    """
    refs: list[str] = []
    in_prompt = False
    for line in content.splitlines():
        stripped = line.strip()

        if in_prompt:
            if not stripped or _TASK_LINE_RE.match(line) or _METADATA_RE.match(stripped):
                in_prompt = False
            else:
                continue

        has_prompt = "_Prompt:" in stripped
        req_match = _REQ_REF_RE.search(line)

        if has_prompt:
            if req_match:
                req_pos = line.find("_Requirements:")
                prompt_pos = line.find("_Prompt:")
                if 0 <= req_pos < prompt_pos:
                    refs.extend(_REQ_ID_RE.findall(req_match.group(1)))
            in_prompt = True
            continue

        if req_match:
            refs.extend(_REQ_ID_RE.findall(req_match.group(1)))
    return refs


def is_bug_fix_content(content: str) -> bool:
    """Return ``True`` when *content* carries bug-fix template headings."""
    for line in content.splitlines():
        if _BUG_FIX_HEADING_RE.match(line.strip()):
            return True
    return False


def analyse_traceability(
    req_content: str, tasks_content: str,
) -> TraceabilityResult:
    """Compare requirement ids to task refs; report coverage gaps."""
    req_ids = extract_requirement_ids(req_content)
    task_refs = extract_task_requirement_refs(tasks_content)

    covered: list[str] = []
    missing_reqs: list[str] = []
    valid_refs: list[str] = []
    orphan_refs: list[str] = []
    req_id_set = set(req_ids)

    for req in req_ids:
        if req in task_refs or any(parent_id(r) == req for r in task_refs):
            covered.append(req)
        else:
            missing_reqs.append(req)

    for ref in sorted(set(task_refs)):
        if ref in req_id_set or parent_id(ref) in req_id_set:
            valid_refs.append(ref)
        else:
            orphan_refs.append(ref)

    has_gap = bool(missing_reqs or orphan_refs)
    return TraceabilityResult(
        result="gaps_found" if has_gap else "full_coverage",
        covered=covered,
        missing=missing_reqs,
        validRefs=valid_refs,
        orphanRefs=orphan_refs,
    )
