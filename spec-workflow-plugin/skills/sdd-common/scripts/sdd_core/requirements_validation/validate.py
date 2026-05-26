"""Public ``validate_content`` entry point — orchestrates each phase."""
from __future__ import annotations

from typing import Any

from ..specs import is_bug_fix_spec
from ..validation_helpers import Severity
from .line_findings import iter_line_findings
from .ruleset import load_ruleset
from .structural import structural_findings
from .types import (
    CANONICAL_GROUPS,
    Finding,
    MODE_BUG_FIX,
    MODE_STANDARD,
    VALID_MODES,
    ValidationOutcome,
)

__all__ = ["validate_content"]


def _sort_findings(findings: list[Finding]) -> list[Finding]:
    sev_order = {Severity.ERROR.value: 0, Severity.WARNING.value: 1, Severity.INFO.value: 2}
    group_order = {g: i for i, g in enumerate(CANONICAL_GROUPS)}
    return sorted(
        findings,
        key=lambda f: (
            sev_order.get(f.get("severity"), 99),
            group_order.get(f.get("group"), 99),
            f.get("line", 0),
            f.get("column", 0),
        ),
    )


def validate_content(
    content: str,
    *,
    mode: str = MODE_STANDARD,
    spec_name: "str | None" = None,
    ruleset: "dict[str, Any] | None" = None,
) -> ValidationOutcome:
    """Validate a requirements.md body.

    Parameters
    ----------
    content:
        Raw markdown text.
    mode:
        Explicit mode override (``"standard"`` or ``"bug-fix"``). When
        omitted and *spec_name* is provided, :func:`is_bug_fix_spec`
        decides.
    spec_name:
        Spec name for auto-detection of bug-fix mode.
    ruleset:
        Pre-loaded ruleset (see :func:`load_ruleset`). Loaded lazily if
        not provided.

    Returns
    -------
    ValidationOutcome
        Dict with ``mode``, ``result``, ``counts``, and ``issues`` keys.
    """
    if mode not in VALID_MODES:
        raise ValueError(
            f"Invalid mode {mode!r}. Must be one of {sorted(VALID_MODES)}"
        )
    if mode == MODE_STANDARD and spec_name and is_bug_fix_spec(spec_name):
        mode = MODE_BUG_FIX

    rs = ruleset or load_ruleset()

    findings: list[Finding] = []
    findings.extend(structural_findings(content, rs))
    findings.extend(iter_line_findings(content, rs, mode=mode))
    findings = _sort_findings(findings)

    counts = {"errors": 0, "warnings": 0, "infos": 0}
    for f in findings:
        sev = f.get("severity")
        if sev == Severity.ERROR.value:
            counts["errors"] += 1
        elif sev == Severity.WARNING.value:
            counts["warnings"] += 1
        elif sev == Severity.INFO.value:
            counts["infos"] += 1

    if counts["errors"] > 0:
        result = "fail"
    elif counts["warnings"] > 0:
        result = "warn"
    elif counts["infos"] > 0:
        result = "info"
    else:
        result = "pass"

    return ValidationOutcome(
        mode=mode,
        result=result,
        counts=counts,
        issues=findings,
    )
