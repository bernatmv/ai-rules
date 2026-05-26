"""Shared session-state validation primitives for PRD workflows.

Used by both write-session-state.py (per-step validation on write) and
validate-readiness.py (gate-level validation on read).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from prd.shared import (
    WHEN_THEN_RE,
    NFR_CATEGORIES,
    NFR_CATEGORY_KEYS,
    count_sentences,
)


@lru_cache(maxsize=1)
def load_problem_statement_markers() -> tuple[str, ...]:
    """Return solution-vocabulary markers for the problem statement.

    Source of truth is
    ``sdd_core/data/requirements_antipatterns.yaml``'s
    ``problem_statement.solution_markers.literals`` list. Returns an
    empty tuple when the YAML file or the section is unavailable —
    callers degrade gracefully. PyYAML-missing is the only observable
    failure (single known remediation: ``pip install pyyaml``); other
    load errors stay silent to preserve best-effort advisory semantics.
    """
    try:
        from sdd_core.deps import require_pyyaml
        from sdd_core.requirements_validation import DATA_FILE
    except Exception:  # noqa: BLE001
        return ()
    try:
        yaml = require_pyyaml()
    except Exception as exc:  # noqa: BLE001
        from sdd_core import output
        output.warn(
            "PRD solution-marker advisory disabled — "
            f"PyYAML unavailable ({exc})."
        )
        return ()
    try:
        with open(DATA_FILE, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except Exception:  # noqa: BLE001 — advisory feature
        return ()
    block = (data or {}).get("problem_statement") or {}
    markers = block.get("solution_markers") or {}
    literals = markers.get("literals") or []
    return tuple(
        str(lit).strip().lower()
        for lit in literals
        if isinstance(lit, str) and lit.strip()
    )


def scan_problem_statement_solution_markers(text: str) -> list[str]:
    """Return solution markers found in *text* (case-insensitive)."""
    if not text:
        return []
    haystack = text.lower()
    hits: list[str] = []
    for marker in load_problem_statement_markers():
        if marker and marker in haystack and marker not in hits:
            hits.append(marker)
    return hits


def validate_problem_statement(text: str, min_sentences: int = 2) -> list[str]:
    """Validate problem statement text meets minimum sentence count."""
    n = count_sentences(text)
    if n < min_sentences:
        return [f"Problem statement has {n} sentence(s), need {min_sentences}+"]
    return []


def validate_goals(goals: list, min_count: int = 2) -> list[str]:
    """Validate goals list has enough entries with required columns."""
    gaps: list[str] = []
    if len(goals) < min_count:
        gaps.append(f"Goals has {len(goals)} entries, need {min_count}+")
    for g in goals:
        missing = [k for k in ("goal", "metric", "target", "measurement_method") if not g.get(k)]
        if missing:
            gaps.append(f"Goal {g.get('id', '?')} missing: {', '.join(missing)}")
    return gaps


def validate_non_goals(non_goals: list, min_count: int = 1) -> list[str]:
    """Validate non-goals list has entries with reasons."""
    gaps: list[str] = []
    if len(non_goals) < min_count:
        gaps.append("Non-goals has no entries")
    for ng in non_goals:
        if not ng.get("reason"):
            gaps.append(f"Non-goal {ng.get('id', '?')} missing reason")
    return gaps


def validate_requirements_when_then(reqs: list) -> list[str]:
    """Validate at least one requirement contains WHEN/THEN pattern."""
    has_wt = any(WHEN_THEN_RE.search(r.get("text", "")) for r in reqs)
    if not has_wt:
        return ["No WHEN/THEN requirements found"]
    return []


def validate_nfr_categories(nfrs: dict) -> list[str]:
    """Validate all 6 NFR category keys are present and non-empty."""
    gaps: list[str] = []
    for cat, key in zip(NFR_CATEGORIES, NFR_CATEGORY_KEYS):
        if not nfrs.get(key):
            gaps.append(f"NFR category '{cat}' not found in session")
    return gaps


def validate_stress_test(stress_test: dict) -> list[str]:
    """Validate stress test structure. Empty ryg_reds allowed when objections resolved."""
    gaps: list[str] = []
    if not stress_test.get("objections"):
        gaps.append("stress_test.objections has no entries")
    if stress_test.get("objections_resolved") is None:
        gaps.append("stress_test.objections_resolved is required")
    ryg_reds = stress_test.get("ryg_reds")
    if ryg_reds is None:
        gaps.append("stress_test.ryg_reds is required")
    elif isinstance(ryg_reds, list) and len(ryg_reds) == 0:
        if not stress_test.get("objections_resolved"):
            gaps.append("stress_test.ryg_reds is empty but objections not resolved")
    return gaps


def validate_open_questions(oqs: list) -> list[str]:
    """Validate open questions have owner, due_date, and blocks."""
    gaps: list[str] = []
    for oq in oqs:
        missing = [k for k in ("owner", "due_date", "blocks") if not oq.get(k)]
        if missing:
            gaps.append(f"Open question {oq.get('id', '?')} missing: {', '.join(missing)}")
    return gaps


def validate_step(step: int, data: dict) -> list[str]:
    """Single dispatcher for per-step business-rule validation."""
    if step == 1:
        return validate_problem_statement(
            (data.get("problem_statement") or {}).get("text", ""))
    if step == 2:
        return validate_goals(data.get("goals", []))
    if step == 3:
        return validate_non_goals(data.get("non_goals", []))
    if step == 4:
        return (validate_requirements_when_then(data.get("requirements", []))
                + validate_nfr_categories(data.get("nfr_categories", {})))
    if step == 5:
        return validate_stress_test(data.get("stress_test", {}))
    return []
