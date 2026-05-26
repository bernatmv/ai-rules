"""Prompt text assembly for review sub-agents.

Builds scoring guidance, tier ownership blocks, artifact shape examples,
and complete sub-agent prompts for both doc reviews and code reviews.

# lint: canonical-owner — review/pipeline_phases/prompt_builder.py is
# the renderer that emits prose containing the five sub-agent input
# keys. The literals enter the prompt verbatim (rendered via
# :mod:`sdd_core.review_input`) so the sub-agent reads the same
# contract names the writer parses.
"""
from __future__ import annotations

from sdd_core import output
from sdd_core.doc_config import DOCUMENT_REGISTRY
from sdd_core.prompts import (
    SUB_AGENT_TWO_STATUS_CONTRACT,
    status_contract_for_scope,
)

from review_quality.constants import (
    PASS_THRESHOLD_PCT, NEEDS_WORK_THRESHOLD_PCT, SCORE_VALUE_MAP,
    TIER1_SCRIPT_SPECS,
    TIER1_FACET_SCOPE_LABELS, DEFAULT_TIER1_NA_SCOPE_LABEL,
)
from review_quality.registry_helpers import (
    facets_for_doc_keys, resolve_doc_keys_from_files,
)
from review_quality.scoring_contract import build_contract_from_doc_list
from sdd_core.review_input import (
    render_artifact_shape_doc_review as _render_artifact_shape_doc_review,
    render_final_scope_demotion_instruction as _render_final_scope_demotion_instruction,
)
from sdd_core.review_quality_schema import (
    FINAL_SCOPE,
    PER_DOCUMENT_SCOPE,
)

from . import get_templates, SUB_AGENT_BOUNDARY, resolve_skill_path
from .resolvers import resolve_template, resolve_verification_file, resolve_staging_path

# ---------------------------------------------------------------------------
# Constants — prompt fragments referenced by build functions
# ---------------------------------------------------------------------------

# Canonical schema for sub-agent input to update-quality.py (doc reviews) is
# rendered by :mod:`sdd_core.review_input` so the contract has one owner;
# this module re-exposes the rendered string under the existing constant
# name so call-sites that import ARTIFACT_SHAPE_DOC_REVIEW keep working.
ARTIFACT_SHAPE_DOC_REVIEW = _render_artifact_shape_doc_review()

FINAL_SCOPE_DEMOTION_INSTRUCTION = _render_final_scope_demotion_instruction()


# Per-finding ``root_cause_kind`` declaration injected near the
# Tier-2 reporting instructions. The sub-agent populates one of these
# values for every actionable finding so the post-review aggregator can
# decide whether the fix lives in this doc or out-of-band.
ROOT_CAUSE_KIND_INSTRUCTION = (
    "Root cause kind (REQUIRED on every actionable finding): When you "
    "record a critical or warning entry under ``tier2_scores[*].findings[]`` "
    "(or a ``conflict`` under ``cross_validation.pairs[*].findings[]``), "
    "populate ``root_cause_kind`` from this enum:\n"
    "  - in_doc: fix lives entirely in the doc(s) under review (default).\n"
    "  - external_state: blocking artifact lives outside this doc "
    "(e.g. missing steering files, unrun migrations, undeployed dependency).\n"
    "  - cross_doc: contradiction between sibling docs in the same spec; "
    "fixing one doc requires editing another.\n"
    "  - criteria_dispute: facet criteria themselves are the wrong test for "
    "this doc; raise with the human reviewer rather than the doc author.\n"
    "Missing ``root_cause_kind`` on an actionable finding is a schema error."
)

# Code review uses dimensions (not facets/doc_keys). Separate shape avoids
# confusing the sub-agent with doc-review concepts.
ARTIFACT_SHAPE_CODE_REVIEW = (
    "Expected update-quality.py --input shape for code review:\n"
    '{"skill_version": "<semver>", "dimensions_reviewed": ["<dim_key>"], '
    '"dimension_scores": {"<dim_key>": {"score": "pass|partial|fail", '
    '"issues": {"critical": 0, "warning": 0, "suggestion": 0}}}, '
    '"testing_thoroughness": "Comprehensive|Adequate|Basic|Insufficient"}'
)

RECORD_DIMENSION_CMD = (
    ".spec-workflow/sdd review/validate-review-progress.py "
    "--phase record --dimension {dim_key} --read-file --checks-cited {N}"
)

# ---------------------------------------------------------------------------
# Scoring guidance builders
# ---------------------------------------------------------------------------


def _in_scope_facets(review_type: str, doc_list: str) -> dict[str, list[dict]]:
    """Return facet lists filtered to the docs named in ``doc_list``.

    Empty / missing ``doc_list`` returns the full registry map (opt-in
    filter).
    """
    target_keys = resolve_doc_keys_from_files(
        review_type, doc_list.split(",") if doc_list else [],
    )
    return facets_for_doc_keys(review_type, target_keys)


def build_scoring_guidance(review_type: str, doc_list: str) -> str:
    """Build scoring instructions derived from the ScoringContract.

    The narrative score denominator is :attr:`ScoringContract.canonical_max`
    — the Tier 2 facet count — so the prompt text cannot drift from the
    post-review denominator. Tier 1 facets are reported separately and
    never contribute to the denominator.
    """
    if review_type not in DOCUMENT_REGISTRY:
        output.error(
            f"No facets found for review_type {review_type!r} in DOCUMENT_REGISTRY",
            hint="Check that 'facets' are defined for this type in doc_config.py",
        )

    contract = build_contract_from_doc_list(review_type, doc_list)
    total_facets = contract.canonical_max

    if total_facets == 0:
        output.error(
            f"No Tier 2 facets for review_type '{review_type}' in DOCUMENT_REGISTRY",
            hint="Check that 'facets' are defined for this type in doc_config.py",
        )

    score_pass = SCORE_VALUE_MAP["pass"]
    score_partial = SCORE_VALUE_MAP["partial"]
    example_pass = total_facets - 1
    example_total = example_pass * score_pass + score_partial
    return (
        f"Score reporting: {contract.narrative_instruction()}\n"
        f"Score mapping: pass={score_pass}, partial={score_partial}, fail=0. "
        "Overall = sum of Tier 2 facet scores.\n"
        f"Example: {example_pass} pass + 1 partial = "
        f"{example_pass * score_pass} + {score_partial} = {example_total}/{total_facets}.\n"
        "Per-facet: use pass/partial/fail only. Do NOT use alternative scales (e.g. 4/5).\n"
        f"Status derivation: PASS if score ≥{PASS_THRESHOLD_PCT}%, "
        f"NEEDS_WORK if ≥{NEEDS_WORK_THRESHOLD_PCT}%, "
        f"FAIL if <{NEEDS_WORK_THRESHOLD_PCT}%. "
        "Use these thresholds exactly — do NOT override with subjective judgment.\n"
        "Authoritative score: the parent agent uses "
        "`artifact_score.value / artifact_score.max` from the post-review "
        "envelope for routing. Your narrative overall score is "
        "informational only; the two values may differ by the "
        "cross-validation deduction, and a narrative PASS is never the "
        "approval signal."
    )


def build_code_review_scoring() -> str:
    """Build scoring guidance for code review (dimension-based, no DOCUMENT_REGISTRY facets)."""
    score_pass = SCORE_VALUE_MAP["pass"]
    score_partial = SCORE_VALUE_MAP["partial"]
    return (
        f"Score reporting: Score each review dimension as "
        f"pass ({score_pass}) / partial ({score_partial}) / fail (0).\n"
        f"Overall = sum of dimension scores. Report as {{total}}/{{max}}.\n"
        "Per-dimension: use pass/partial/fail only. "
        "Do NOT use alternative scales (e.g. 4/5).\n"
        f"Status derivation: PASS if score ≥{PASS_THRESHOLD_PCT}%, "
        f"NEEDS_WORK if ≥{NEEDS_WORK_THRESHOLD_PCT}%, "
        f"FAIL if <{NEEDS_WORK_THRESHOLD_PCT}%. "
        "Use these thresholds exactly — do NOT override with subjective judgment."
    )


def tier_ownership_block(review_type: str, doc_list: str = "") -> str:
    """Build tier ownership instructions from DOCUMENT_REGISTRY and TIER1_SCRIPT_SPECS.

    When ``doc_list`` is provided, the block only mentions facets whose
    doc is actually under review — a per-document review of ``tech.md``
    should not list ``product.md`` / ``structure.md`` facets the sub-agent
    was told to ignore, which inflated the tier list to 15 entries
    against a 5-point scoring cap.
    """
    reg = DOCUMENT_REGISTRY.get(review_type, {})
    filtered = _in_scope_facets(review_type, doc_list)
    in_scope_facet_ids = {
        f["id"] for facet_list in filtered.values() for f in facet_list
    }
    tier1_ids: set[str] = set()
    for script_name in reg.get("tier1_scripts", []):
        spec = TIER1_SCRIPT_SPECS.get(script_name, {})
        tier1_ids.update(spec.get("covers", []))
    # Tier-1 facets whose covering doc is outside the review scope
    # must not surface in the emitted block; otherwise the sub-agent
    # reports "don't score tech_md_x" entries it was never asked to see.
    tier1_ids = tier1_ids & in_scope_facet_ids if in_scope_facet_ids else tier1_ids
    tier2_ids = sorted(in_scope_facet_ids - tier1_ids)

    if not tier1_ids and not tier2_ids:
        return ""
    return (
        f"Tier 1 (script-owned, do NOT include in tier2_scores): {sorted(tier1_ids)}\n"
        f"Tier 2 (your responsibility, MUST include in tier2_scores): {tier2_ids}\n"
    )


def build_tier2_facet_criteria_by_scope(
    review_type: str, doc_list: str = "",
) -> dict[str, dict[str, str]]:
    """Map of facet IDs whose criteria differ between per-doc and final scope.

    Each value is ``{"per-document": "<criteria text>", "final":
    "<criteria text>"}`` so the sub-agent can compare the two and
    populate ``final_scope_demotions_predicted[]`` when its per-doc
    rating would not survive the final-scope criteria.

    Today no facet declares scope-specific criteria — the registry
    carries one criterion per facet that applies at every scope. The
    helper returns an empty dict so the launch envelope ships the field
    structurally. Future facets opt in by adding a ``scope_specific_criteria``
    entry to their :data:`DOCUMENT_REGISTRY` row; this helper lifts that
    mapping into the launch envelope without touching call sites.
    """
    reg = DOCUMENT_REGISTRY.get(review_type, {})
    if not reg:
        return {}
    filtered = _in_scope_facets(review_type, doc_list)
    out: dict[str, dict[str, str]] = {}
    for facet_list in filtered.values():
        for facet in facet_list:
            scope_specific = facet.get("scope_specific_criteria")
            if not isinstance(scope_specific, dict):
                continue
            per_doc = scope_specific.get(PER_DOCUMENT_SCOPE)
            final = scope_specific.get(FINAL_SCOPE)
            if per_doc and final and per_doc != final:
                out[str(facet["id"])] = {
                    PER_DOCUMENT_SCOPE: str(per_doc),
                    FINAL_SCOPE: str(final),
                }
    return out


def tier1_scope_label_block(review_type: str, doc_list: str = "") -> str:
    """Per-facet scope labels for ``na`` Tier-1 entries the sub-agent surfaces.

    The narrative template instructs the sub-agent to render every
    ``na`` Tier-1 facet as ``na (scope: <facet scope label>)``. The
    label data lives in
    :data:`review_quality.constants.TIER1_FACET_SCOPE_LABELS` so the
    prompt and the registry stay in sync; missing entries fall back
    to :data:`review_quality.constants.DEFAULT_TIER1_NA_SCOPE_LABEL`
    so the rendered prompt is never broken.
    """
    reg = DOCUMENT_REGISTRY.get(review_type, {})
    if not reg.get("tier1_scripts"):
        return ""
    filtered = _in_scope_facets(review_type, doc_list)
    in_scope_facet_ids = {
        f["id"] for facet_list in filtered.values() for f in facet_list
    }
    facet_ids: set[str] = set()
    for script_name in reg.get("tier1_scripts", []):
        spec = TIER1_SCRIPT_SPECS.get(script_name, {})
        facet_ids.update(spec.get("covers", []))
    if in_scope_facet_ids:
        facet_ids &= in_scope_facet_ids
    if not facet_ids:
        return ""
    lines = ["Tier-1 facet scope labels (substitute when rendering `na`):"]
    for facet_id in sorted(facet_ids):
        label = TIER1_FACET_SCOPE_LABELS.get(
            facet_id, DEFAULT_TIER1_NA_SCOPE_LABEL,
        )
        lines.append(f"  - {facet_id}: {label}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Full prompt assembly
# ---------------------------------------------------------------------------


def build_doc_review_prompt(
    review_skill: str, target_name: str, project_path: str,
    doc_list: str, category: str, review_type: str,
    prd_file_path: str | None = None,
    scope: str | None = None,
) -> tuple[str, str, str]:
    """Build doc-review sub-agent prompt, skill path, and verification file path.

    Returns (prompt, review_skill_path, verification_file).

    ``per-document`` scope drops the artifact-completeness line —
    future docs are out of scope at this gate.
    """
    template = resolve_template(review_skill)
    review_skill_path = resolve_skill_path(review_skill)
    prompt = template.format(
        review_skill_path=review_skill_path,
        target_name=target_name,
        project_path=project_path,
        doc_list=doc_list,
    )

    prompt += "\n\n" + build_scoring_guidance(review_type, doc_list)

    tier_block = tier_ownership_block(review_type, doc_list)
    if tier_block:
        prompt += "\n\n" + tier_block

    scope_label_block = tier1_scope_label_block(review_type, doc_list)
    if scope_label_block:
        prompt += "\n\n" + scope_label_block

    if prd_file_path:
        prompt += f"\n\nPRD file path (pre-resolved): {prd_file_path}\n"

    prompt += "\n\n" + ARTIFACT_SHAPE_DOC_REVIEW
    prompt += "\n\n" + ROOT_CAUSE_KIND_INSTRUCTION
    if scope == PER_DOCUMENT_SCOPE:
        # The reconciliation only matters at per-document scope: a
        # final-scope review already evaluates final criteria directly,
        # so demotion predictions would be redundant.
        prompt += "\n\n" + FINAL_SCOPE_DEMOTION_INSTRUCTION
    prompt += "\n\n" + status_contract_for_scope(scope)
    prompt += SUB_AGENT_BOUNDARY

    verification_file = resolve_verification_file(category, target_name)
    return prompt, review_skill_path, verification_file


def build_code_review_prompt(
    review_skill: str, target_name: str, project_path: str,
    category: str,
) -> tuple[str, str, str, str]:
    """Build code-review sub-agent prompt with scoring, progress, and staging.

    Returns (prompt, review_skill_path, verification_file, scoring_guidance).
    """
    review_skill_path = resolve_skill_path(review_skill)
    template = resolve_template(review_skill)
    prompt = template.format(
        review_skill_path=review_skill_path,
        target_name=target_name,
        project_path=project_path,
        doc_list="",
    )

    scoring_guidance = build_code_review_scoring()
    prompt += "\n\n" + scoring_guidance

    prompt += (
        "\n\nAfter completing each review dimension, record progress:\n"
        f"  {RECORD_DIMENSION_CMD}\n"
        "Do NOT batch-complete all dimensions — record each one individually."
    )

    prompt += "\n\n" + ARTIFACT_SHAPE_CODE_REVIEW

    staging_path = resolve_staging_path(
        category, target_name, project_path,
    )
    from sdd_core.command_templates import build_update_quality_command
    update_quality_cmd = build_update_quality_command(
        review_type=category,
        scope=None,
        staging_path=staging_path,
    ).render()
    prompt += (
        f"\n\nAssessment staging: Write intermediate assessment JSON to "
        f"`{staging_path}` (NOT /tmp/). "
        f"Then pass this path to `{update_quality_cmd}`."
    )
    prompt += "\n\n" + SUB_AGENT_TWO_STATUS_CONTRACT
    prompt += SUB_AGENT_BOUNDARY

    verification_file = resolve_verification_file(category, target_name)
    return prompt, review_skill_path, verification_file, scoring_guidance
