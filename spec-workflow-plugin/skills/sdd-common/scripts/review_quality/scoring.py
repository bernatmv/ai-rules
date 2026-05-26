"""Pure scoring derivation functions — no I/O, no side effects.

Cross-validation deduction constants (``CV_DEDUCTION_PER_FINDING`` /
``CV_MAX_DEDUCTION``) are retained but the default deduction applied
by :func:`apply_cross_validation_cap` is zero — duplication findings
route through the ``informational`` bucket of the report so they
surface to the reader without docking the score. Callers that want
the legacy "dock the score" behaviour can pass
``max_deduction=CV_MAX_DEDUCTION`` explicitly.
"""

from __future__ import annotations

import re

__all__ = [
    "normalize_score",
    "recompute_doc_score",
    "derive_doc_status",
    "derive_overall_status",
    "derive_overall_score",
    "aggregate_facet_issues",
    "apply_cross_validation_cap",
    "count_cv_findings",
    "derive_comprehension_confidence",
    "derive_comprehension_fields",
    "CANONICAL_MAX",
]

from .registry import (
    empty_score, PASSING_CONFIDENCE_LEVELS, DOC_STATUS_THRESHOLDS,
)
from .constants import (
    CV_DEDUCTION_PER_FINDING, CV_MAX_DEDUCTION,
    SCOPE_PER_DOCUMENT, STRUCTURAL_NA_PREFIX,
)

CANONICAL_MAX = 15

_SCORE_PATTERNS = [
    (re.compile(r"(\d+(?:\.\d+)?)\s*/\s*(\d+)"), lambda m: (float(m.group(1)), float(m.group(2)))),
    (re.compile(r"(\d+(?:\.\d+)?)\s+out\s+of\s+(\d+)"), lambda m: (float(m.group(1)), float(m.group(2)))),
    (re.compile(r"(\d+(?:\.\d+)?)\s*%"), lambda m: (float(m.group(1)) / 100 * CANONICAL_MAX, float(CANONICAL_MAX))),
]


def normalize_score(raw_score: str, expected_max: int = CANONICAL_MAX) -> dict:
    """Normalize a raw score string to {total}/{max} format.

    Returns dict with keys: normalized, original, was_compliant, and
    either warning (str|None) or error (str).
    """
    raw_score = raw_score.strip()

    for pattern, extractor in _SCORE_PATTERNS:
        match = pattern.search(raw_score)
        if match:
            total, max_val = extractor(match)

            if int(max_val) == expected_max:
                normalized = f"{total:g}/{int(max_val)}"
                is_compliant = normalized == raw_score
                return {
                    "normalized": normalized,
                    "original": raw_score,
                    "was_compliant": is_compliant,
                    "warning": None if is_compliant else (
                        f"Score '{raw_score}' normalized to '{normalized}'"
                    ),
                }

            scaled_total = round(total / max_val * expected_max, 1)
            normalized = f"{scaled_total:g}/{expected_max}"
            return {
                "normalized": normalized,
                "original": raw_score,
                "was_compliant": False,
                "warning": (
                    f"Score '{raw_score}' used non-standard scale "
                    f"({int(max_val)}-point); converted to '{normalized}' "
                    f"({expected_max}-point scale)"
                ),
            }

    return {
        "normalized": None,
        "original": raw_score,
        "was_compliant": False,
        "error": f"Could not parse score from '{raw_score}'",
    }


_ISSUE_SEVERITIES = ("critical", "warning", "suggestion")


def aggregate_facet_issues(documents: dict) -> dict:
    """Thin wrapper over :func:`findings.collect_findings`.

    Returns per-severity counts for facet_issue findings only.
    """
    from .findings import collect_findings

    totals = {sev: 0 for sev in _ISSUE_SEVERITIES}
    for f in collect_findings({"documents": documents}):
        if f.source == "facet_issue" and f.severity in totals:
            totals[f.severity] += 1
    return totals


def recompute_doc_score(facets: list[dict]) -> dict:
    """Pure function: compute {value, max, percent} from facets list.

    Three ``na`` branches:

    - ``na`` with ``na_justification`` starting with
      :data:`STRUCTURAL_NA_PREFIX` — facet is structurally
      inapplicable to this spec (e.g. removal/parity facets on a
      purely-additive feature). Dropped from both ``value`` and
      ``max`` so the denominator stays honest.
    - ``na`` with any other ``na_justification`` — explicit
      reviewer opt-out. Contributes 0 to ``value`` but still counts
      toward ``max`` so a sub-agent cannot inflate percent by
      dodging difficult facets.
    - bare ``na`` (no justification) — auto-inserted "missing
      facet" placeholder. Dropped from the denominator so
      coverage-complete reviews still pass cleanly.
    """
    value = 0.0
    max_score = 0
    for facet in facets:
        sv = facet.get("score_value")
        if sv is not None:
            value += sv
            max_score += 1
            continue
        if facet.get("score") == "na" and facet.get("na_justification"):
            justification = str(facet["na_justification"])
            if justification.startswith(STRUCTURAL_NA_PREFIX):
                continue
            max_score += 1
    percent = round(value / max_score * 100) if max_score > 0 else 0
    return {"value": value, "max": max_score, "percent": percent}


def derive_doc_status(score: dict, facets: list) -> str:
    value = score.get("value", 0)
    max_s = score.get("max", 0)
    if max_s == 0:
        return "INCOMPLETE"
    ratio = value / max_s
    has_critical = any(
        f.get("score") == "fail" and f.get("issues", {}).get("critical", 0) > 0
        for f in facets
    )
    if has_critical or ratio < DOC_STATUS_THRESHOLDS["fail_below"]:
        return "FAIL"
    if ratio >= DOC_STATUS_THRESHOLDS["pass_at_or_above"]:
        return "PASS"
    return "NEEDS_WORK"


def doc_keys_for_scope(
    scope: str | None,
    all_doc_keys: list,
    reviewed_keys: list | set,
) -> list:
    """Return the doc_keys that should drive ``overall_status`` for *scope*.

    ``per-document`` scope ignores future docs (status is derived only
    over the docs the sub-agent actually examined this gate).
    ``final`` scope (default) keeps the full required-doc list — every
    expected doc must be present at the final gate.

    Single source of truth — used by :func:`derive_overall_status`
    callers and by sub-agent narrative builders so the artifact's
    ``overall_status`` and the narrative's ``Reviewed-docs status``
    cannot drift. Callers must pass a validated scope (one of
    :data:`review_quality.constants.REVIEW_SCOPES`); this function does
    not normalise case.
    """
    if scope == SCOPE_PER_DOCUMENT:
        reviewed = set(reviewed_keys or [])
        return [k for k in all_doc_keys if k in reviewed]
    return list(all_doc_keys)


def derive_overall_status(
    documents: dict,
    doc_keys: list,
    *,
    artifact: dict | None = None,
) -> str:
    """Derive overall status including advisory-signal rollup.

    The per-doc statuses define the score band; :mod:`signal_rollup`
    consumes that band and upgrades ``PASS`` → ``PASS_WITH_ADVISORIES``
    when any registered advisory signal is adverse. Callers can pass a
    synthetic ``artifact`` dict when they want the rollup to inspect
    documents / cross_validation fields that live outside *documents*.
    """
    statuses = [documents.get(k, {}).get("status", "INCOMPLETE") for k in doc_keys]
    if "INCOMPLETE" in statuses:
        return "INCOMPLETE"
    if all(s == "PASS" for s in statuses):
        score_band = "PASS"
    else:
        tier1_all_pass = all(
            documents.get(k, {}).get("template_compliance") in ("PASS", None)
            for k in doc_keys
        )
        if "FAIL" in statuses and not tier1_all_pass:
            score_band = "FAIL"
        else:
            score_band = "NEEDS_WORK"

    from .signal_rollup import worst_status

    rollup_artifact = artifact if artifact is not None else {"documents": documents}
    return worst_status(rollup_artifact, score_band=score_band)


def count_cv_findings(cv_data: dict | None) -> int:
    """Count total duplication + conflict findings across all cross-validation pairs.

    Single source of truth — used by both apply_cross_validation_cap and
    update-quality.py findings consistency checks.
    """
    if not cv_data or not isinstance(cv_data, dict):
        return 0
    pairs = cv_data.get("pairs", {})
    return sum(
        pair.get("duplications", 0) + pair.get("conflicts", 0)
        for pair in pairs.values()
        if isinstance(pair, dict)
    )


#: Default deduction applied to cross-validation findings. Zero by
#: default — duplication findings are informational, not score-docking.
#: Callers can pass an explicit ``max_deduction`` to re-enable the
#: legacy deduction.
CV_DEFAULT_DEDUCTION = 0.0


def apply_cross_validation_cap(
    raw_score: dict | None,
    cross_validation_data: dict | None,
    max_deduction: float = CV_DEFAULT_DEDUCTION,
) -> tuple[dict | None, float]:
    """Return ``(adjusted_score, deduction_applied)`` for CV findings.

    The default deduction is zero so duplication findings surface as
    informational signal rather than score noise. A non-zero
    ``max_deduction`` reinstates the legacy behaviour
    (``CV_DEDUCTION_PER_FINDING`` per finding, capped at the override).
    """
    if raw_score is None or cross_validation_data is None:
        return raw_score, 0.0
    findings_count = count_cv_findings(cross_validation_data)
    if findings_count == 0 or max_deduction <= 0:
        return raw_score, 0.0
    deduction = min(findings_count * CV_DEDUCTION_PER_FINDING, max_deduction)
    raw_score["value"] = max(raw_score["value"] - deduction, 0)
    total_max = raw_score.get("max", 0)
    raw_score["percent"] = round(raw_score["value"] / total_max * 100) if total_max > 0 else 0
    return raw_score, deduction


def derive_overall_score(
    documents: dict, doc_keys: list, overall_status: str
) -> dict | None:
    if overall_status == "INCOMPLETE":
        return None
    total_value = 0.0
    total_max = 0
    for k in doc_keys:
        s = documents.get(k, {}).get("score", empty_score())
        total_value += s.get("value", 0)
        total_max += s.get("max", 0)
    percent = round(total_value / total_max * 100) if total_max > 0 else 0
    return {"value": total_value, "max": total_max, "percent": percent}


def derive_comprehension_confidence(questions: list) -> str:
    if not questions:
        return "LOW"
    confidences = [q.get("confidence", "LOW") for q in questions]
    if all(c == "HIGH" for c in confidences):
        return "HIGH"
    if any(c == "LOW" for c in confidences):
        return "LOW"
    return "MEDIUM"


def derive_comprehension_fields(comp_input: dict, all_reviewed: bool) -> dict:
    """Derive aggregate fields for ai_comprehension_test / implementation_readiness."""
    questions = comp_input.get("questions", [])
    confidence = derive_comprehension_confidence(questions)
    questions_passed = sum(1 for q in questions if q.get("confidence") in PASSING_CONFIDENCE_LEVELS)
    questions_total = len(questions)
    full_test = comp_input.get("full_test")
    if not all_reviewed:
        full_test = None
    full_test_passed = None
    if all_reviewed and full_test:
        full_test_passed = full_test.get("confidence") in PASSING_CONFIDENCE_LEVELS
    return {
        "confidence": confidence,
        "questions_passed": questions_passed,
        "questions_total": questions_total,
        "full_test_passed": full_test_passed,
        "questions": questions,
        "full_test": full_test,
    }
