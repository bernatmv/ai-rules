"""Typed contract for sub-agent assessment input fed to update-quality.py.

Single source of truth for the JSON shape sub-agents emit and the script
parses. Two renderers consume this contract: prompt rendering for the
sub-agent, and shape-only validation for the script. ``RootCauseKind``,
``ROOT_CAUSE_KINDS`` and ``ReviewScore`` are imported from
:mod:`sdd_core.review_quality_schema` — never redefined here.

# lint: canonical-owner — sdd_core.review_input owns the five
# top-level sub-agent input keys. Every other reader imports the
# named constants from this module instead of restating the literal.
"""
from __future__ import annotations

from typing import Any, Literal, TypedDict

try:  # NotRequired added in Python 3.11
    from typing import NotRequired
except ImportError:  # pragma: no cover - Python 3.9/3.10 path
    from typing_extensions import NotRequired

from sdd_core.review_quality_schema import (
    ROOT_CAUSE_KINDS,
    ReviewScore,
    RootCauseKind,
)

__all__ = [
    "FacetIssueCounts",
    "FacetFinding",
    "FacetScore",
    "FinalScopeDemotion",
    "SubAgentAssessmentInput",
    "INPUT_TOP_LEVEL_KEYS",
    "INPUT_KEY_SKILL_VERSION",
    "INPUT_KEY_DOCUMENTS_REVIEWED",
    "INPUT_KEY_TIER2_SCORES",
    "INPUT_KEY_CROSS_VALIDATION",
    "INPUT_KEY_TESTING_THOROUGHNESS",
    "INPUT_KEY_FINAL_SCOPE_DEMOTIONS_PREDICTED",
    "render_artifact_shape_doc_review",
    "render_final_scope_demotion_instruction",
    "validate_assessment_input",
    "ROOT_CAUSE_KINDS",
    "RootCauseKind",
    "ReviewScore",
]


# Named aliases keep call sites readable while the canonical literal
# stays single-sourced under ``INPUT_TOP_LEVEL_KEYS``.
INPUT_KEY_SKILL_VERSION = "skill_version"
INPUT_KEY_DOCUMENTS_REVIEWED = "documents_reviewed"
INPUT_KEY_TIER2_SCORES = "tier2_scores"
INPUT_KEY_CROSS_VALIDATION = "cross_validation"
INPUT_KEY_TESTING_THOROUGHNESS = "testing_thoroughness"
INPUT_KEY_FINAL_SCOPE_DEMOTIONS_PREDICTED = "final_scope_demotions_predicted"

INPUT_TOP_LEVEL_KEYS: tuple[str, ...] = (
    INPUT_KEY_SKILL_VERSION,
    INPUT_KEY_DOCUMENTS_REVIEWED,
    INPUT_KEY_TIER2_SCORES,
    INPUT_KEY_CROSS_VALIDATION,
    INPUT_KEY_TESTING_THOROUGHNESS,
    INPUT_KEY_FINAL_SCOPE_DEMOTIONS_PREDICTED,
)


class FacetIssueCounts(TypedDict):
    critical: int
    warning: int
    suggestion: int


class FacetFinding(TypedDict):
    severity: Literal["critical", "warning"]
    summary: str
    root_cause_kind: RootCauseKind


class FacetScore(TypedDict):
    id: str
    score: ReviewScore
    issues: FacetIssueCounts
    findings: NotRequired[list[FacetFinding]]


class FinalScopeDemotion(TypedDict):
    facet_id: str
    per_document_score: ReviewScore
    predicted_final_score: ReviewScore
    reason: str


class SubAgentAssessmentInput(TypedDict):
    skill_version: str
    documents_reviewed: list[str]
    tier2_scores: dict[str, list[FacetScore]]
    cross_validation: NotRequired[dict[str, Any]]
    testing_thoroughness: NotRequired[str]
    final_scope_demotions_predicted: NotRequired[list[FinalScopeDemotion]]


def render_artifact_shape_doc_review() -> str:
    """Render the canonical sub-agent input shape line — the verbatim contract."""
    return (
        "Expected update-quality.py --input shape:\n"
        '{"skill_version": "<semver>", "documents_reviewed": ["<doc_key>"], '
        '"tier2_scores": {"<doc_key>": [{"id": "<facet_id>", "score": "pass|partial|fail", '
        '"issues": {"critical": 0, "warning": 0, "suggestion": 0}, '
        '"findings": [{"severity": "critical|warning", "summary": "<one-line>", '
        '"root_cause_kind": "in_doc|external_state|cross_doc|criteria_dispute"}]}]}, '
        '"cross_validation": {"pairs": {"<doc_a>_x_<doc_b>": {"findings": [...]}}}, '
        '"testing_thoroughness": "Comprehensive|Adequate|Basic|Insufficient"}'
    )


def render_final_scope_demotion_instruction() -> str:
    """Render the cross-scope reconciliation instruction.

    The placement is the input root (NOT under ``tier2_scores``); the
    script's ``build_artifact`` reads the field from the input root.
    """
    return (
        "Cross-scope criteria reconciliation: the launch envelope's "
        "``tier2_facet_criteria_by_scope`` map names facets whose criteria "
        "differ between per-document and final scope. For every such facet "
        "you score ``pass`` at per-document scope, evaluate the final-scope "
        "criteria as well; when the per-doc rating would NOT survive the "
        "final-scope rules (e.g. a cross-document consistency check that "
        "only applies once siblings exist), append a row to "
        "``final_scope_demotions_predicted[]`` at the input root (NOT under "
        "``tier2_scores``): ``{\"facet_id\": \"<id>\", \"per_document_score\": "
        "\"pass\", \"predicted_final_score\": \"partial|fail\", \"reason\": "
        "\"<one-line>\"}``. An empty list is the correct answer when no "
        "demotions are predicted or when ``tier2_facet_criteria_by_scope`` "
        "is empty."
    )


_REQUIRED_KEYS: tuple[str, ...] = (
    INPUT_KEY_SKILL_VERSION,
    INPUT_KEY_DOCUMENTS_REVIEWED,
    INPUT_KEY_TIER2_SCORES,
)


def validate_assessment_input(
    data: dict, *, mode: Literal["warn", "raise"] = "warn",
) -> list[str]:
    """Return shape-only validation errors for sub-agent input.

    ``mode == "raise"`` raises :class:`ValueError` when errors exist;
    ``mode == "warn"`` returns the list and lets the caller route the
    advisory through ``output.partial`` or an envelope payload field.

    Note: ships in warn mode (one release of telemetry); flip default
    to ``"raise"`` once production telemetry shows zero warnings for
    one cycle.
    """
    # TODO: once warn-mode telemetry shows zero warnings for one full
    # release cycle, flip the default to ``raise`` and remove this
    # comment alongside the warn/raise branch. Keep the signature
    # stable so callers that pass mode= explicitly stay working.
    errors: list[str] = []
    if not isinstance(data, dict):
        msg = f"input must be a JSON object; got {type(data).__name__}"
        if mode == "raise":
            raise ValueError(msg)
        return [msg]

    for key in _REQUIRED_KEYS:
        if key not in data:
            errors.append(f"missing required key {key!r}")

    tier2 = data.get("tier2_scores")
    if "tier2_scores" in data and not isinstance(tier2, dict):
        errors.append(
            f"tier2_scores must be a dict; got {type(tier2).__name__}"
        )

    documents_reviewed = data.get("documents_reviewed")
    if "documents_reviewed" in data and not isinstance(documents_reviewed, list):
        errors.append(
            f"documents_reviewed must be a list; got "
            f"{type(documents_reviewed).__name__}"
        )

    demotions = data.get("final_scope_demotions_predicted")
    if demotions is not None:
        if not isinstance(demotions, list):
            errors.append(
                "final_scope_demotions_predicted must be a list at the input "
                f"root; got {type(demotions).__name__}"
            )
        else:
            for idx, row in enumerate(demotions):
                if not isinstance(row, dict):
                    errors.append(
                        f"final_scope_demotions_predicted[{idx}] must be a "
                        f"dict; got {type(row).__name__}"
                    )

    cross_validation = data.get("cross_validation")
    if cross_validation is not None and not isinstance(cross_validation, dict):
        errors.append(
            f"cross_validation must be a dict when present; got "
            f"{type(cross_validation).__name__}"
        )

    if errors and mode == "raise":
        raise ValueError("; ".join(errors))
    return errors
