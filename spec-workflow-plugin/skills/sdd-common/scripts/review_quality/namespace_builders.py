"""Per-type context and supplemental builder dispatch."""
from __future__ import annotations

import dataclasses
from typing import Callable

from sdd_core.review_input import INPUT_KEY_TESTING_THOROUGHNESS

from .supplemental import (
    _build_testing_thoroughness,
    _build_design_principles_scorecard,
    _build_anti_pattern_detections,
)


@dataclasses.dataclass(frozen=True)
class BuildContext:
    """Shared state available to all namespace builders."""
    review_type: str
    spec_name: str
    prior: dict | None
    all_reviewed: bool


def _build_spec_context(input_data: dict, ctx: BuildContext) -> dict:
    return {
        "spec_name": ctx.spec_name or input_data.get("spec_name", ""),
        "spec_type": input_data.get("spec_type", "standard"),
    }


def _build_steering_context(input_data: dict, ctx: BuildContext) -> dict:
    return {}


def _build_prd_context(input_data: dict, ctx: BuildContext) -> dict:
    return {"spec_name": ctx.spec_name or input_data.get("spec_name", "")}


_CONTEXT_BUILDERS: dict[str, Callable[[dict, BuildContext], dict]] = {
    "spec":     _build_spec_context,
    "steering": _build_steering_context,
    "prd":      _build_prd_context,
}


def _build_spec_supplemental(input_data: dict, ctx: BuildContext) -> dict:
    tt_input = input_data.get(INPUT_KEY_TESTING_THOROUGHNESS)
    if tt_input is not None:
        tt = _build_testing_thoroughness(tt_input)
    elif ctx.all_reviewed:
        tt = None
    else:
        tt = ctx.prior.get("supplemental", ctx.prior).get(INPUT_KEY_TESTING_THOROUGHNESS) if ctx.prior else None
    return {INPUT_KEY_TESTING_THOROUGHNESS: tt}


def _build_steering_supplemental(input_data: dict, ctx: BuildContext) -> dict:
    return {
        "design_principles_scorecard": _build_design_principles_scorecard(
            input_data.get("design_principles_scorecard")
        )
    }


def _build_prd_supplemental(input_data: dict, ctx: BuildContext) -> dict:
    return {
        "anti_pattern_detections": _build_anti_pattern_detections(
            input_data.get("anti_pattern_detections")
        )
    }


_SUPPLEMENTAL_BUILDERS: dict[str, Callable[[dict, BuildContext], dict]] = {
    "spec":     _build_spec_supplemental,
    "steering": _build_steering_supplemental,
    "prd":      _build_prd_supplemental,
}
