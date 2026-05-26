"""Pipeline check-revalidation phase: after fixes, check if re-review is needed."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from sdd_core import output
from sdd_core.command_templates import build_review_launch_command
from sdd_core.doc_config import skill_name_for_category
from sdd_core.paths import doc_dir_path
from review_quality.staleness import is_doc_stale
from review_quality.gate_session import (
    GATE_FIX_CYCLE,
    GATE_LAUNCH_ARGS_CACHE,
    GATE_LAUNCH_FLAGS,
    GATE_REVIEW_GATE,
    write_session, advance_gate,
)
from review_quality.constants import (
    DEFAULT_MAX_FIX_CYCLES, DEFAULT_REVIEW_SCOPE,
)

from ..phase_kit import Phase, PhaseContext, PhaseInput, phase
from . import (
    phase_entry_guard, build_phase_cmd, build_prompt_cmd,
    load_quality_data, quality_file_path,
)
from .constants import PHASE_CHECK_REVALIDATION, PHASE_PRE_APPROVAL


def _handle_check_revalidation(
    ctx: PhaseContext, inp: "CheckRevalidationInput",
) -> None:
    """After fixes applied, check if re-review is needed for a single document.

    Lifecycle fields (``category`` / ``target_name`` / ``project_path``)
    arrive via :class:`PhaseContext`; phase-specific flags via
    :class:`CheckRevalidationInput`.
    """
    spec_name = ctx.target_name
    category = ctx.category
    project_path = ctx.project_path

    session, blocked = phase_entry_guard(category, spec_name, project_path, PHASE_CHECK_REVALIDATION)
    if blocked:
        output.success(blocked, blocked["reason"])
        return

    doc = inp.doc
    fix_cycle = inp.fix_cycle
    max_cycles = inp.max_cycles

    doc_directory = doc_dir_path(category, spec_name, project_path)
    doc_path = os.path.join(doc_directory, doc)
    q_path = quality_file_path(category, spec_name, project_path)

    if not os.path.isfile(doc_path):
        output.success({
            "re_review_required": False,
            "fix_cycle": fix_cycle,
            "max_cycles": max_cycles,
            "can_continue": False,
            "next_action": "proceed",
            "reason": f"Document {doc} does not exist.",
        }, "No document found")
        return

    if not os.path.isfile(q_path):
        output.success({
            "re_review_required": False,
            "fix_cycle": fix_cycle,
            "max_cycles": max_cycles,
            "can_continue": True,
            "next_action": "proceed",
            "reason": "No review-quality.json found. First review not run yet.",
        }, "No prior review")
        return

    quality_data = load_quality_data(category, spec_name, project_path) or {}

    gate = session.get(GATE_REVIEW_GATE) or {}
    persisted_cycle = gate.get(GATE_FIX_CYCLE, 0)
    if fix_cycle == 0 and persisted_cycle > 0:
        fix_cycle = persisted_cycle

    doc_modified_after_review = is_doc_stale(doc_path, quality_data, doc)

    can_continue = fix_cycle < max_cycles
    if doc_modified_after_review:
        next_action = "re-review" if can_continue else "proceed"
    else:
        next_action = "proceed"

    cached = session.get(GATE_LAUNCH_ARGS_CACHE, {})

    lf = cached.get('lifecycle_flags', '')
    # Re-launch flag round-trip via the canonical emitter — single
    # owner for both first launch and re-launch literals so the
    # rendered string is byte-equal modulo ``--fix-cycle`` /
    # ``--gate-id`` deltas. ``gate["launch_flags"]`` is the persisted
    # full set; fall back to ``launch_args_cache`` when
    # ``launch_flags`` is absent.
    persisted_launch_flags = (
        gate.get(GATE_LAUNCH_FLAGS)
        or {
            "review_skill": cached.get("review_skill")
            or skill_name_for_category(category),
            "doc_list": cached.get("doc_list", doc),
            "scope": cached.get("scope", DEFAULT_REVIEW_SCOPE),
        }
    )
    if doc_modified_after_review and can_continue:
        next_action_command = build_review_launch_command(
            launch_flags=persisted_launch_flags,
            locator={
                "category": category,
                "target_name": spec_name,
                "project_path": cached.get("project_path", project_path),
            },
            fix_cycle=fix_cycle + 1,
            gate_id=ctx.gate_id or persisted_launch_flags.get("gate_id"),
        )
    else:
        next_action_command = build_phase_cmd(
            PHASE_PRE_APPROVAL,
            project_path=cached.get('project_path', project_path),
            category=category,
            target_name=spec_name,
            extra_args=f'--doc-list "{cached.get("doc_list", doc)}"',
            lifecycle_flags=lf,
        )

    exclude_opts = ["accept"] if doc_modified_after_review else []

    prompt_command = build_prompt_cmd(
        "fix-loop-continue",
        f"fix_cycle={fix_cycle} max_fix_cycles={max_cycles}",
        exclude_opts=exclude_opts,
    )

    result = {
        "re_review_required": doc_modified_after_review,
        "fix_cycle": fix_cycle,
        "max_cycles": max_cycles,
        "can_continue": can_continue,
        "next_action": next_action,
        "next_action_command": next_action_command,
        "prompt_command": prompt_command,
        "post_fix_user_choices_excluded": exclude_opts,
        "reason": (
            f"Document modified after review — re-review needed."
            if doc_modified_after_review
            else "Review is current. Proceed to approval."
        ),
    }

    if doc_modified_after_review and can_continue:
        session = advance_gate(session, required_next_phase="launch")
    else:
        session = advance_gate(session, required_next_phase=PHASE_PRE_APPROVAL)
    write_session(category, spec_name, session, project_path)

    output.success(result, "Re-review check complete")


@dataclass
class CheckRevalidationInput(PhaseInput):
    """Typed input for the ``check-revalidation`` phase.

    Lifecycle fields live on the common parent parser; only
    phase-specific flags are declared here.
    """

    doc: str = field(
        default=None, metadata={
            "help": "Document filename (e.g. requirements.md)",
        },
    )
    fix_cycle: int = field(
        default=0, metadata={"help": "Current fix cycle"},
    )
    max_cycles: int = field(
        default=DEFAULT_MAX_FIX_CYCLES, metadata={"help": "Max cycles"},
    )


@phase(
    name=PHASE_CHECK_REVALIDATION,
    emits=frozenset({"launch", PHASE_PRE_APPROVAL}),
    help="After fixes, check if re-review is needed",
    description=__doc__,
)
class CheckRevalidationPhase(Phase):
    """Re-validation branch — decides whether a fixed document needs
    another review cycle or can advance to pre-approval.
    """

    Input = CheckRevalidationInput

    def handle(self, ctx: PhaseContext, inp: CheckRevalidationInput) -> None:
        _handle_check_revalidation(ctx, inp)
