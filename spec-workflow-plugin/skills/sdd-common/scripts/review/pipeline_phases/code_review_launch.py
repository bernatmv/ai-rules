"""Generate sub-agent prompt for post-implementation code review (no gate session)."""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field

from sdd_core import cli, output, paths
from sdd_core.command_templates import placeholder_note

from ..phase_kit import Phase, PhaseInput, phase
from .prompt_builder import build_code_review_prompt, RECORD_DIMENSION_CMD
from .resolvers import resolve_staging_path


def _record_dimension_placeholder_note() -> str:
    """Canonical substitution note for ``RECORD_DIMENSION_CMD`` placeholders."""
    return placeholder_note(
        ("dim_key", "N"),
        source="the dimension you just finished reviewing",
    )


def handle_code_review_launch(args: argparse.Namespace) -> None:
    """Generate sub-agent prompt for post-implementation code review (no gate session)."""
    review_skill = args.review_skill
    # Fallback differs from other phases: code-review-launch defaults
    # target_name to ``"spec"`` (no gate session means no category-based
    # scaffold), so ``PhaseContext.from_args`` is not reused here.
    target_name = args.target_name or "spec"
    review_category: str = args.category
    project_path = paths.resolve_project_path(args)

    prompt, review_skill_path, verification_file, scoring_guidance = (
        build_code_review_prompt(
            review_skill, target_name, project_path, review_category,
        )
    )

    staging_path = resolve_staging_path(
        review_category, target_name, project_path,
    )

    progress_checklist = (
        "## Code Review Checklist\n\n"
        "- [ ] Read review skill (sdd-review-code)\n"
        "- [ ] Evaluate each dimension, recording via validate-review-progress.py\n"
        f"- [ ] Write assessment JSON to staging path ({staging_path})\n"
        f"- [ ] Run update-quality.py --input {staging_path}\n"
        "- [ ] Verify review-quality.json exists\n"
        "- [ ] Return scores and findings\n\n"
        "Copy this checklist to track progress."
    )

    output.success(
        {
            "sub_agent_prompt": prompt,
            "review_skill_path": review_skill_path,
            "verification_file": verification_file,
            "assessment_staging_path": staging_path,
            "progress_commands": {
                "record_dimension": RECORD_DIMENSION_CMD,
                "placeholder_substitution_note": _record_dimension_placeholder_note(),
            },
            "progress_checklist": progress_checklist,
            "score_normalization": {
                "instruction": scoring_guidance,
                "expected_format": "{total}/{max}",
                "conversion_formula": "scaled = total / max * 100 (percent)",
            },
            "next_action_command": (
                f"Launch a Task sub-agent with the sub_agent_prompt above. "
                f"The sub-agent should read {review_skill_path} and follow the review workflow."
            ),
        },
        f"Code review launch prepared for {target_name}",
    )


@dataclass
class CodeReviewLaunchInput(PhaseInput):
    """Typed input for the ``code-review-launch`` entry phase.

    Lifecycle fields live on the common parent parser; only
    phase-specific flags are declared here.
    """

    review_skill: str = field(
        default=None, metadata={
            "help": "Review skill name (e.g. sdd-review-code)",
        },
    )


@phase(
    name="code-review-launch",
    emits=frozenset(),
    help="Generate sub-agent prompt for post-implementation code review",
    description=__doc__,
)
class CodeReviewLaunchPhase(Phase):
    """Entry-style phase — prepares the post-implementation code review
    sub-agent prompt. Declared in :data:`review.transitions.ENTRY_PHASES`
    so the reachability property test treats it as standalone.
    """

    Input = CodeReviewLaunchInput

    def handle(self, args: argparse.Namespace) -> None:
        handle_code_review_launch(args)
