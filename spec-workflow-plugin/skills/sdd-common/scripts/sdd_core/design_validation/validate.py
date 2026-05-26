"""Run design.md against the YAML antipattern ruleset."""
from __future__ import annotations

import re
from typing import Any

from ..text import iter_indexed_lines
from .ruleset import load_ruleset
from .types import Finding, ValidationOutcome

__all__ = ["validate_content"]


_ATX_HEADER_RE = re.compile(r"^(#{1,6})\s+\S")


def _iter_content_lines(content: str) -> list[tuple[int, str]]:
    """Return ``(lineno, raw)`` pairs (1-indexed), skipping frontmatter / fences.

    Wraps :func:`sdd_core.text.iter_indexed_lines` so the "what counts
    as content" definition stays identical to ``requirements_validation``.
    """
    return [(idx + 1, raw) for idx, raw in iter_indexed_lines(content)]


def _check_acceptance_criteria_as_design(
    lines: list[tuple[int, str]], rule: dict[str, Any],
) -> list[Finding]:
    """Flag EARS-style ``WHEN ... THEN system SHALL`` lines in design.md."""
    pat = re.compile(
        r"\b(WHEN|IF)\b.+\bTHEN\b.+\bsystem\s+SHALL\b",
        re.IGNORECASE,
    )
    findings: list[Finding] = []
    for lineno, text in lines:
        if pat.search(text):
            findings.append({
                "severity": rule.get("severity", "error"),
                "rule": rule["id"],
                "line": lineno,
                "message": rule["message"],
                "suggestion": rule.get("suggestion"),
            })
    return findings


def _check_task_list_as_design(
    lines: list[tuple[int, str]], rule: dict[str, Any],
) -> list[Finding]:
    """Flag markdown task-list bullets (``- [ ]`` / ``- [x]``)."""
    pat = re.compile(r"^\s*[-*]\s*\[[ xX]\]")
    findings: list[Finding] = []
    for lineno, text in lines:
        if pat.match(text):
            findings.append({
                "severity": rule.get("severity", "error"),
                "rule": rule["id"],
                "line": lineno,
                "message": rule["message"],
                "suggestion": rule.get("suggestion"),
            })
    return findings


def _check_prose_only_no_component_headers(
    content: str, lines: list[tuple[int, str]], rule: dict[str, Any],
) -> list[Finding]:
    """Flag design.md with no ATX headers below H1.

    The first finding lands on the first non-blank line below H1 (or
    line 1 when no H1 is present); reviewers see "this design is one
    block of prose" rather than a column-by-column line list.
    """
    headers = []
    for lineno, text in lines:
        m = _ATX_HEADER_RE.match(text)
        if m:
            headers.append((lineno, len(m.group(1)), text.strip()))
    has_sub = any(level > 1 for _, level, _ in headers)
    if has_sub:
        return []
    target = 1
    for lineno, text in lines:
        if text.strip():
            target = lineno
            break
    return [{
        "severity": rule.get("severity", "warning"),
        "rule": rule["id"],
        "line": target,
        "message": rule["message"],
        "suggestion": rule.get("suggestion"),
    }]


_DISPATCH = {
    "acceptance-criteria-as-design": _check_acceptance_criteria_as_design,
    "task-list-as-design": _check_task_list_as_design,
}


def validate_content(content: str) -> ValidationOutcome:
    """Validate a design.md body against the YAML ruleset."""
    rs = load_ruleset()
    rules: list[dict[str, Any]] = rs.get("rules") or []
    lines = _iter_content_lines(content)

    issues: list[Finding] = []
    for rule in rules:
        rid = rule.get("id")
        if not rid:
            continue
        if rid == "prose-only-no-component-headers":
            issues.extend(
                _check_prose_only_no_component_headers(content, lines, rule)
            )
        else:
            handler = _DISPATCH.get(rid)
            if handler is not None:
                issues.extend(handler(lines, rule))

    counts = {"errors": 0, "warnings": 0, "infos": 0}
    for f in issues:
        sev = f.get("severity", "error")
        if sev == "error":
            counts["errors"] += 1
        elif sev == "warning":
            counts["warnings"] += 1
        else:
            counts["infos"] += 1

    if counts["errors"] > 0:
        result = "fail"
    elif counts["warnings"] > 0:
        result = "warn"
    elif counts["infos"] > 0:
        result = "info"
    else:
        result = "pass"

    issues.sort(key=lambda f: (f.get("line", 0), f.get("rule", "")))
    return ValidationOutcome(result=result, counts=counts, issues=issues)
