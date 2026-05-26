"""Structured-findings view for ``validate_content`` output.

Single producer of the wire-shape consumed by ``pre_check.py`` and
the ``lint-requirements.py`` CLI. Decouples the on-disk
``Finding`` representation from the agent-facing JSON envelope.
"""
from __future__ import annotations

from typing import Iterable

from .types import Finding, GROUP_FIX_HINTS

__all__ = ["build_structured_findings"]


def build_structured_findings(
    issues: Iterable[Finding] | Iterable[dict],
    content: str,
) -> list[dict]:
    """Normalise validator findings for downstream consumers.

    Produces ``rule_id``, ``group``, ``severity``, ``line``, ``column``,
    ``snippet`` (enclosing source line, stripped), ``match`` and
    ``fix_hint`` keys. ``message`` and ``section`` from the underlying
    :class:`Finding` are preserved for callers that already depend on
    them.
    """
    lines = content.splitlines()
    structured: list[dict] = []
    for issue in issues:
        line_no = issue.get("line") or 0
        snippet = ""
        if 1 <= line_no <= len(lines):
            snippet = lines[line_no - 1].strip()
        fix_hint = issue.get("suggestion") or GROUP_FIX_HINTS.get(
            issue.get("group", ""), "Revise per requirements-antipatterns.md.",
        )
        structured.append({
            "rule_id": issue.get("rule", ""),
            "group": issue.get("group", ""),
            "severity": issue.get("severity", ""),
            "line": line_no,
            "column": issue.get("column", 0),
            "snippet": snippet,
            "match": issue.get("match", ""),
            "fix_hint": fix_hint,
            "message": issue.get("message", ""),
            "section": issue.get("section", ""),
        })
    return structured
