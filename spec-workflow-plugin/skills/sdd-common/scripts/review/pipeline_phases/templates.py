"""Sub-agent prompt templates for review pipeline phases."""
from __future__ import annotations

from review_quality.constants import REVIEW_QUALITY_FILENAME

# Canonical headline phrasing the sub-agent must echo verbatim in its
# narrative response. Lifting the literal here keeps the prompt
# template, the agent-facing guidelines doc, and the post-review echo
# verifier in lockstep — none of them retypes the phrase. The
# placeholders are NOT substituted by ``str.format`` here (the prompt
# template's own ``.format(...)`` only substitutes
# ``{review_skill_path}`` / ``{target_name}`` / etc., so the doubled
# braces below survive that pass and emerge as single braces for the
# sub-agent to read). The shape mirrors the gate-rendered headline in
# :func:`review.pipeline_phases.post_review._render_gate_score_headline`
# so the sub-agent narrative and the gate emit a single literal — no
# divergence vector between gate-computed status and sub-agent prose.
OVERALL_STATUS_NARRATIVE_TEMPLATE = (
    "Reviewed-docs status: {{overall_status}} "
    "(gate score: {{gate_score_value}}/{{gate_score_max}}; "
    "Tier 1 facets: {{tier1_summary}})"
)

# Per-category artifact location the sub-agent verifies wrote to disk after a review.
VERIFICATION_PATHS = {
    "spec": f".spec-workflow/specs/{{target_name}}/{REVIEW_QUALITY_FILENAME}",
    "steering": f".spec-workflow/steering/{REVIEW_QUALITY_FILENAME}",
    "discovery": f".spec-workflow/discovery/{{target_name}}/{REVIEW_QUALITY_FILENAME}",
}

# Trailing prompt block fencing scripts that only the parent agent may invoke.
SUB_AGENT_BOUNDARY = (
    "\n\nBOUNDARY: Do NOT call any of these scripts — they are managed by the parent agent:\n"
    "  - review/prepare-pipeline.py (pipeline orchestration)\n"
    "  - approval/*.py (approval lifecycle)\n"
    "  - spec/create-snapshot.py (snapshot management)\n"
    "Your scope: read the review skill → review documents → "
    "write quality artifact via review/update-quality.py → return scores."
)


def _build_skill_templates() -> dict[str, str]:
    """Build sub-agent prompt templates from DOCUMENT_REGISTRY."""
    # Deferred: lazy-init avoids import-time side effects from DOCUMENT_REGISTRY
    from sdd_core.doc_config import DOCUMENT_REGISTRY

    _SKILL_EXTRAS: dict[str, dict] = {
        "sdd-review-spec-docs": {
            "params_extra": "  - Spec name: {target_name}\n",
            "return_extra": "",
        },
        "sdd-review-steering-docs": {
            "params_extra": "",
            "return_extra": "",
        },
        "sdd-review-prd": {
            "params_extra": "  - Feature name: {target_name}\n",
            "pre_instructions": (
                "PRD is located via discovery manifest, NOT spec status:\n"
                "  1. Read manifest at .spec-workflow/discovery/{target_name}/manifest.json\n"
                "  2. Filter artifacts where type == \"prd\"\n"
                "  3. PRD file path: .spec-workflow/discovery/{target_name}/{{prd_name}}\n"
                "\n"
                "Do NOT use spec/check-status.py for PRD discovery — "
                "it only searches .spec-workflow/specs/.\n\n"
            ),
            "return_extra": ", anti-pattern detections",
        },
        "sdd-review-code": {
            "params_extra": "  - Mode: spec-aware\n  - Spec name: {target_name}\n",
            "skip_doc_list": True,
            "post_instructions": (
                "Follow all steps in the skill. "
                "When in standalone mode, skip spec-only steps.\n"
            ),
            "return_text": (
                "Return: Overall score, per-dimension results "
                "(dimension name + score + pass/fail),\n"
                "findings list with severities "
                "(file, line, description, recommendation),\n"
                "positive observations, and executive summary."
            ),
        },
    }

    templates: dict[str, str] = {}
    seen_skills: set[str] = set()

    for rtype, reg in DOCUMENT_REGISTRY.items():
        skill_name = reg["skill_name"]
        if skill_name in seen_skills:
            continue
        seen_skills.add(skill_name)

        extras = _SKILL_EXTRAS.get(skill_name, {})
        params_extra = extras.get("params_extra", f"  - Target: {{target_name}}\n")
        pre_instructions = extras.get("pre_instructions", "")
        post_instructions = extras.get("post_instructions",
                                        "Follow all steps in the skill.\n")
        category = reg.get("category", rtype)
        verification = VERIFICATION_PATHS.get(category, VERIFICATION_PATHS["spec"])

        if extras.get("return_text"):
            return_block = extras["return_text"]
        else:
            return_extra = extras.get("return_extra", "")
            # ``{{gate_score_headline}}`` is doubled so it survives the
            # prompt template's first ``.format(...)`` pass (which
            # substitutes ``{review_skill_path}`` etc.) and lands as
            # ``{gate_score_headline}`` for the second pass —
            # :func:`launch._apply_post_review_substitutions` replaces
            # it with the literal headline persisted on the prior
            # :class:`PostReviewSnapshot`. When no prior snapshot exists
            # (first launch) the placeholder remains and the sub-agent
            # falls back to rendering ``OVERALL_STATUS_NARRATIVE_TEMPLATE``.
            return_block = (
                "Return: Headline narrative line on row 1 — when the gate "
                "ships a literal under {{gate_score_headline}} echo it "
                "verbatim; otherwise render "
                f"'{OVERALL_STATUS_NARRATIVE_TEMPLATE}' (substitute the values "
                "from the artifact you wrote: gate_score_value / "
                "gate_score_max come from the gate-authoritative score, "
                "tier1_summary lists pass/fail/na counts across Tier 1 "
                "facets). The narrative echoes the gate's literal verbatim "
                "so the prose agrees with the artifact's `overall_status`. "
                "Then: per-facet results "
                "(facet name + score + pass/fail; "
                "render `na` Tier-1 facets as 'na (scope: <facet scope label>)' "
                "so a reader knows why they are not in scope),\n"
                f"issues list with severities{return_extra}, "
                "and confirmation of artifact creation."
            )

        doc_list_param = "" if extras.get("skip_doc_list") else \
            "  - Available documents: {doc_list}\n"

        templates[skill_name] = (
            f"You are reviewing documents for quality using {skill_name}. "
            f"Follow the SDD review skill workflow exactly.\n"
            f"\n"
            f"Read the skill file FIRST:\n"
            f"  {{review_skill_path}}\n"
            f"\n"
            f"Parameters:\n"
            f"{params_extra}"
            f"  - Project path: {{project_path}}\n"
            f"{doc_list_param}"
            f"\n"
            f"{pre_instructions}"
            f"All SDD script invocations MUST use the shim runner:\n"
            f"  .spec-workflow/sdd {{{{group}}}}/{{{{script}}}}.py [args...]\n"
            f"\n"
            f"{post_instructions}"
            f"\n"
            f"Verification: After completion, confirm that the file\n"
            f"  {verification}\n"
            f"exists.\n"
            f"\n"
            f"{return_block}"
        )

    # Code review is not a document type (no DOCUMENT_REGISTRY entry).
    # Build its template directly from _SKILL_EXTRAS.
    cr_extras = _SKILL_EXTRAS.get("sdd-review-code", {})
    if cr_extras and "sdd-review-code" not in templates:
        params_extra = cr_extras.get("params_extra", "")
        post_inst = cr_extras.get("post_instructions", "")
        return_text = cr_extras.get("return_text", "")
        templates["sdd-review-code"] = (
            "You are performing a post-implementation code review "
            "using sdd-review-code. "
            "Follow the SDD review skill workflow exactly.\n"
            "\n"
            "Read the skill file FIRST:\n"
            "  {review_skill_path}\n"
            "\n"
            "Parameters:\n"
            f"{params_extra}"
            "  - Project path: {project_path}\n"
            "\n"
            f"{post_inst}"
            "\n"
            "All SDD script invocations MUST use the shim runner:\n"
            "  .spec-workflow/sdd {{group}}/{{script}}.py [args...]\n"
            "\n"
            "Verification: After completion, confirm that the file\n"
            f"  {VERIFICATION_PATHS['spec']}\n"
            "exists.\n"
            "\n"
            f"{return_text}"
        )

    return templates


_TEMPLATES: dict[str, str] | None = None


def get_templates() -> dict[str, str]:
    global _TEMPLATES
    if _TEMPLATES is None:
        _TEMPLATES = _build_skill_templates()
    return _TEMPLATES
