"""Supplemental data normalization (testing thoroughness, design principles, anti-patterns)."""
from __future__ import annotations

from .constants import DESIGN_PRINCIPLE_WEIGHT

_POINTS_PER_PRINCIPLE = 2  # max weight per principle — aligns with DESIGN_PRINCIPLE_WEIGHT["HIGH"]


def _build_testing_thoroughness(tt_input: dict | str | None) -> dict | None:
    """Normalize testing_thoroughness from string or object input."""
    if tt_input is None:
        return None
    if isinstance(tt_input, str):
        return {"rating": tt_input, "summary": []}
    if isinstance(tt_input, dict):
        return {
            "rating": tt_input.get("rating", ""),
            "summary": [s for s in tt_input.get("summary", []) if isinstance(s, str)],
        }
    return None


def _build_design_principles_scorecard(dp_input: dict | None) -> dict | None:
    if dp_input is None:
        return None
    ratings = dp_input.get("ratings", [])
    scored = [r for r in ratings if DESIGN_PRINCIPLE_WEIGHT.get(r.get("rating")) is not None]
    score_val = sum(DESIGN_PRINCIPLE_WEIGHT[r["rating"]] for r in scored)
    return {
        "score": {"value": score_val, "max": len(scored) * _POINTS_PER_PRINCIPLE},
        "ratings": ratings,
    }


def _build_anti_pattern_detections(raw: list | None) -> list:
    """Normalize anti_pattern_detections: keep only detected entries, strip unknown fields."""
    if not raw:
        return []
    if not isinstance(raw, list):
        return []
    result = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        if not entry.get("detected", False):
            continue
        result.append({
            k: v for k, v in entry.items()
            if k in ("pattern", "section", "severity", "detected", "description")
        })
    return result
