"""Section-map, suppression, and severity resolution helpers.

Carves out the "metadata per line" concerns from the finding-emission
logic in ``line_findings`` so each function has a tight single job.
"""
from __future__ import annotations

import re
from typing import Any

from ..validation_helpers import Severity
from .types import (
    MODE_BUG_FIX,
    SUPPRESSION_ALIASES,
    SUPPRESSION_TAG_RE,
)

__all__ = [
    "build_section_map",
    "collect_suppressions",
    "resolve_severity",
]


def build_section_map(content: str) -> dict[int, str]:
    """Map 0-based line indices to their enclosing H2 heading text.

    Walks **every** line (including those inside code fences) so the
    returned mapping covers suppressor scan lines too — we intentionally
    do not reuse ``iter_content_lines`` here, because that helper skips
    fenced lines. Fence-internal H2 markers are ignored for section
    tracking (a doc-style convention: ``##`` inside a fence is example
    text, not a real heading).
    """
    mapping: dict[int, str] = {}
    current = ""
    heading_re = re.compile(r"^(#{1,6})\s+(.*)")
    in_fence = False
    for i, line in enumerate(content.splitlines()):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            mapping[i] = current
            continue
        if in_fence:
            mapping[i] = current
            continue
        m = heading_re.match(line)
        if m and m.group(1) == "##":
            current = m.group(2).strip()
        mapping[i] = current
    return mapping


def collect_suppressions(content: str) -> dict[int, set[str]]:
    """Return ``{target_line_index: {group, …}}`` for each rq-ignore comment.

    A comment on line N suppresses findings whose match lands on line N+1
    (the immediately following non-comment line). Blank lines are
    transparent — we scan forward until a non-blank line is reached.
    """
    lines = content.splitlines()
    suppressions: dict[int, set[str]] = {}
    for idx, raw in enumerate(lines):
        for m in SUPPRESSION_TAG_RE.finditer(raw):
            group = m.group("group").lower()
            # Coarse-grained ``rq-ignore`` tags (e.g. ``architecture``)
            # expand into the fine-grained canonical group set so one
            # comment can clear both split-group findings.
            aliased = SUPPRESSION_ALIASES.get(group)
            targets = {group} | set(aliased) if aliased else {group}
            j = idx + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines):
                suppressions.setdefault(j, set()).update(targets)
    return suppressions


def resolve_severity(
    group: dict[str, Any],
    *,
    rule: "dict[str, Any] | None",
    section: str,
    mode: str,
) -> Severity:
    """Resolve effective severity for a finding.

    Precedence (highest first):
      1. Rule-level bug_fix_override (when mode == bug-fix)
      2. Group-level bug_fix_override (when mode == bug-fix)
      3. Section-aware severity (e.g. NFR downgrade)
      4. Group default_severity
    """
    default = Severity(group["default_severity"])

    if mode == MODE_BUG_FIX:
        if rule and rule.get("bug_fix_override"):
            return Severity(rule["bug_fix_override"]["severity"])
        if group.get("bug_fix_override"):
            return Severity(group["bug_fix_override"]["severity"])

    section_aware = group.get("section_aware") or {}
    for key, sev_value in section_aware.items():
        if key.lower() in section.lower():
            return Severity(sev_value)

    return default
