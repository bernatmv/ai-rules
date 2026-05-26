"""Review-quality artifact migration steps.

Importing this module registers all review-quality migration steps
with the shared framework. The caller (review_quality/io.py) must
import this module before calling migrate().
"""

from __future__ import annotations

from typing import Any

from migrations import (
    register, relocate_fields, rename_fields, transform_nested,
    transpose_namespace_map,
)
from sdd_core.doc_config import TYPE_NAMESPACE_MAP


_V3_FIELD_DESTINATIONS = transpose_namespace_map(TYPE_NAMESPACE_MAP)


_V3_SKILL_TO_REVIEW_TYPE: dict = {
    "sdd-review-spec-docs": "spec",
    "sdd-review-steering-docs": "steering",
    "sdd-review-prd": "prd",
}

_V3_COMPREHENSION_RENAMES: dict = {
    "ai_comprehension_test": "comprehension",
    "implementation_readiness": "comprehension",
    "sdd_readiness": "comprehension",
}


@register("1.0.0", "2.0.0")
def _migrate_v1_to_v2(data: dict) -> dict:
    """Convert legacy history {first, previous} → {runs: [...]}."""
    _v2_migrate_history(data)
    return data


def _v2_migrate_history(data: dict) -> None:
    history = data.get("history") or {}
    if "runs" in history or ("first" not in history and "previous" not in history):
        return
    first = history.get("first")
    previous = history.get("previous")
    if first is None:
        data["history"] = {"runs": []}
        return
    if previous is None or first.get("at") == previous.get("at"):
        data["history"] = {"runs": [first]}
    else:
        data["history"] = {"runs": [first, previous]}


def _add_percent(score: Any) -> Any:
    """Add percent to a score dict if missing. Idempotent."""
    if isinstance(score, dict) and "percent" not in score:
        score["percent"] = (
            round(score["value"] / score["max"] * 100)
            if score.get("max", 0) > 0 else 0
        )
    return None


@register("2.0.0", "3.0.0")
def _migrate_v2_to_v3(data: dict) -> dict:
    """Migrate schema 2.x artifact to 3.0.0."""
    _v3_add_review_type(data)
    rename_fields(data, _V3_COMPREHENSION_RENAMES)
    relocate_fields(data, _V3_FIELD_DESTINATIONS)
    transform_nested(data, "documents.*.score", _add_percent)
    _v3_normalize_overall_score(data)
    return data


def _v3_add_review_type(data: dict) -> None:
    data.setdefault(
        "review_type",
        _V3_SKILL_TO_REVIEW_TYPE.get(data.get("skill", ""), "unknown"),
    )


def _v3_normalize_overall_score(data: dict) -> None:
    """Normalize legacy 'na' sentinel to null at top level and in history."""
    if data.get("overall_score") == "na":
        data["overall_score"] = None
    history = data.get("history") or {}
    for run in history.get("runs", []):
        if run.get("overall_score") == "na":
            run["overall_score"] = None
