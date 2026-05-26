"""Pipeline ack-calls phase: clear pending_tool_calls after the agent executes them."""
from __future__ import annotations

import argparse
from dataclasses import dataclass

from sdd_core import output
from sdd_core.command_templates import (
    PostFixRecommendation,
    build_check_revalidation_command,
    build_post_fix_command_with_recommended,
)
from review_quality.constants import (
    CURSOR_ADVANCE_USER_CHOICES,
    DEFAULT_MAX_FIX_CYCLES,
    RECOMMENDED_CHOICE_ACCEPT,
    SCOPE_PER_DOCUMENT,
)
from review_quality.gate_session import (
    GATE_FIX_CYCLE,
    GATE_LAUNCH_ARGS_CACHE,
    GATE_MAX_CYCLES,
    GATE_PENDING_CALLS,
    GATE_PENDING_CALLS_ACKED_SIGNATURE,
    GATE_PENDING_CALLS_SIGNATURE,
    GATE_REVIEW_GATE,
    get_phase_snapshot,
    read_session,
    record_executed_signature,
    write_session,
)

from ..phase_kit import Phase, PhaseContext, PhaseInput, phase
from ..snapshots import PostReviewSnapshot
from .._routing import NextOptions, route_with_ack
from .constants import (
    ADVISORY_CODE_CURSOR_ADVANCED, ADVISORY_LEVEL_INFO,
    KEY_ADVISORIES, KEY_LAST_COMPLETED_PHASE, KEY_LAST_COMPLETED_USER_CHOICE,
    PHASE_ACK_CALLS, PHASE_CHECK_REVALIDATION,
    PHASE_POST_FIX, PHASE_POST_REVIEW,
)
from .guards import hash_tool_calls


def _harness_mismatches(pending: list, active_harness: str) -> list[dict]:
    """Return dismissal records for entries whose ``harness_name``
    disagrees with the active adapter.

    Entries without a ``harness_name`` tag are considered universal and
    never dismissed — only entries that name a specific harness and
    name it wrong are surfaced.
    """
    mismatches: list[dict] = []
    for entry in pending or []:
        if not isinstance(entry, dict):
            continue
        entry_harness = entry.get("harness_name")
        if not entry_harness or entry_harness == active_harness:
            continue
        mismatches.append(
            {
                "kind": entry.get("kind") or entry.get("tool") or "unknown",
                "expected_harness": entry_harness,
                "active_harness": active_harness,
            }
        )
    return mismatches


def handle_ack_calls(args: argparse.Namespace) -> None:
    """Clear pending_tool_calls from the gate session after agent executes them.

    Resolves the active adapter and surfaces harness-mismatched entries
    under ``dismissed_mismatch`` so the pipeline is not deadlocked by a
    stale Cursor-shaped TodoWrite when the live harness is Claude Code
    (or vice versa).
    """
    ctx = PhaseContext.from_args(args)
    category = ctx.category
    target_name = ctx.target_name
    project_path = ctx.project_path

    session = read_session(category, target_name, project_path)
    gate = session.get(GATE_REVIEW_GATE) or {}
    cleared = gate.get(GATE_PENDING_CALLS, []) or []

    from sdd_core.harness import HarnessContradictionError, try_load_adapter

    mismatches: list[dict] = []
    try:
        active = try_load_adapter(project_path).name
    except HarnessContradictionError:
        # Adapter state is explicitly malformed — treat any tagged
        # pending call as harness-mismatched so the gate session
        # clears instead of deadlocking on a stale state file.
        mismatches = [
            {
                "kind": entry.get("kind") or entry.get("tool") or "unknown",
                "expected_harness": entry.get("harness_name", "unknown"),
                "active_harness": "unknown",
            }
            for entry in (cleared or [])
            if isinstance(entry, dict) and entry.get("harness_name")
        ]
    else:
        mismatches = _harness_mismatches(cleared, active)

    # Stamp the acked signature before clearing pending so subsequent
    # phase emits can detect "this exact payload was already executed
    # this gate" and suppress redundant re-emission. Falls back to the
    # freshly-computed signature when the persist side never wrote one
    # (e.g. legacy sessions migrated mid-gate).
    pending_signature = gate.get(GATE_PENDING_CALLS_SIGNATURE) or ""
    if not pending_signature and cleared:
        pending_signature = hash_tool_calls(cleared)
    if pending_signature:
        gate[GATE_PENDING_CALLS_ACKED_SIGNATURE] = pending_signature
        record_executed_signature(gate, pending_signature)
    gate[GATE_PENDING_CALLS] = []
    gate[GATE_PENDING_CALLS_SIGNATURE] = ""
    write_session(category, target_name, session, project_path)

    payload: dict = {
        "cleared_calls": len(cleared),
        "status": "acknowledged",
    }
    if mismatches:
        payload["dismissed_mismatch"] = mismatches

    _emit_forward_step(payload, ctx, session)


def _build_post_fix_recommended(
    *,
    ctx: PhaseContext,
    session: dict,
    findings_count: int,
    fix_cycle: int,
    scope: str,
) -> PostFixRecommendation:
    """Compose the literal post-fix command + its recommended choice."""
    cached = session.get(GATE_LAUNCH_ARGS_CACHE) or {}
    gate = session.get(GATE_REVIEW_GATE) or {}
    doc_list = cached.get("doc_list", "") or ""
    max_cycles = int(
        gate.get(GATE_MAX_CYCLES, 0) or cached.get("max_fix_cycles", 0)
        or DEFAULT_MAX_FIX_CYCLES
    )
    return build_post_fix_command_with_recommended(
        category=ctx.category,
        target_name=ctx.target_name,
        project_path=cached.get("project_path", ctx.project_path) or "",
        doc_list=doc_list,
        fix_cycle=fix_cycle,
        max_cycles=max_cycles,
        scope=scope,
        findings_count=findings_count,
        parent_todo=ctx.parent_todo or "",
        gate_id=ctx.gate_id or "",
    )


def _emit_cursor_advance(
    payload: dict, ctx: PhaseContext, session: dict, last_choice: str,
) -> bool:
    """Route forward to check-revalidation when post-fix has just attested.

    Returns ``True`` when the cursor short-circuit fired (the caller
    should not continue to the snapshot path).
    """
    gate_state = session.get(GATE_REVIEW_GATE) or {}
    cached = session.get(GATE_LAUNCH_ARGS_CACHE) or {}
    doc_list = cached.get("doc_list", "")
    primary_doc = doc_list.split(",")[0].strip() if doc_list else ""
    if not primary_doc:
        return False
    forward_cmd = build_check_revalidation_command(
        category=ctx.category,
        target_name=ctx.target_name,
        project_path=cached.get("project_path", ctx.project_path) or "",
        doc=primary_doc,
        fix_cycle=int(gate_state.get(GATE_FIX_CYCLE, 0) or 0),
        max_cycles=int(gate_state.get(GATE_MAX_CYCLES, 0) or 0),
        gate_id=ctx.gate_id or "",
        parent_todo=ctx.parent_todo or "",
    )
    advisories = payload.setdefault(KEY_ADVISORIES, [])
    advisories.append(output.advisory(
        f"workflow position advanced past post-fix --user-choice {last_choice}; "
        "routing forward to check-revalidation",
        level=ADVISORY_LEVEL_INFO,
        code=ADVISORY_CODE_CURSOR_ADVANCED,
    ))
    lifecycle_flags = cached.get("lifecycle_flags", "")
    route_with_ack(
        payload, ctx,
        forward_phase=PHASE_CHECK_REVALIDATION,
        forward_cmd=forward_cmd,
        pending_instr="",
        clear_instr=(
            f"post-fix --user-choice {last_choice} attested. "
            "Run check-revalidation verbatim."
        ),
        lifecycle_flags=lifecycle_flags,
    )
    output.success(
        payload,
        f"Acknowledged {payload.get('cleared_calls', 0)} pending tool call(s)",
    )
    return True


def _emit_forward_step(
    payload: dict, ctx: PhaseContext, session: dict,
) -> None:
    """Emit the literal next step after ack-calls clears.

    Three-clause dispatcher: cursor short-circuit (post-fix just
    attested), no-snapshot fallback (re-run post-review), then the
    snapshot-driven branch that builds the post-fix recommendation.
    """
    gate_state = session.get(GATE_REVIEW_GATE) or {}
    last_phase = gate_state.get(KEY_LAST_COMPLETED_PHASE)
    last_choice = gate_state.get(KEY_LAST_COMPLETED_USER_CHOICE)
    if (
        last_phase == PHASE_POST_FIX
        and last_choice in CURSOR_ADVANCE_USER_CHOICES
        and _emit_cursor_advance(payload, ctx, session, last_choice)
    ):
        return

    snap = get_phase_snapshot(
        session, PHASE_POST_REVIEW, cls=PostReviewSnapshot,
    )
    if snap is None:
        cached = session.get(GATE_LAUNCH_ARGS_CACHE) or {}
        from . import build_phase_cmd
        lifecycle_flags = (
            cached.get("lifecycle_flags", "")
            or (
                f" --parent-todo {ctx.parent_todo} --gate-id {ctx.gate_id}"
                if ctx.parent_todo and ctx.gate_id
                else ""
            )
        )
        rerun_cmd = build_phase_cmd(
            PHASE_POST_REVIEW,
            project_path=cached.get("project_path", ctx.project_path) or "",
            category=ctx.category,
            target_name=ctx.target_name,
            lifecycle_flags=lifecycle_flags,
        )
        problems = [
            "ack-calls: no post-review snapshot to derive next step.",
        ]
        output.recoverable_miss(
            {"reason": "ack_calls_missing_post_review_snapshot"},
            "ack-calls: no post-review snapshot to derive next step",
            next_action_command_sequence=rerun_cmd,
            problems=problems,
            hint=(
                f"{problems[0]} ack-calls reached without a cached "
                "post-review snapshot; re-run post-review to populate "
                "gate state — execute next_action_command_sequence, "
                "then retry."
            ),
        )

    cached = session.get(GATE_LAUNCH_ARGS_CACHE) or {}
    gate = session.get(GATE_REVIEW_GATE) or {}
    findings_count = int(getattr(snap, "actionable_findings", 0) or 0)
    fix_cycle = int(gate.get("fix_cycle", 0) or 0)
    scope = (
        gate.get("review_scope")
        or cached.get("scope", SCOPE_PER_DOCUMENT)
    )
    lifecycle_flags = (
        getattr(snap, "lifecycle_flags", "")
        or cached.get("lifecycle_flags", "")
        or ""
    )

    rec = _build_post_fix_recommended(
        ctx=ctx,
        session=session,
        findings_count=findings_count,
        fix_cycle=fix_cycle,
        scope=scope,
    )

    if findings_count == 0:
        route_with_ack(
            payload, ctx,
            forward_phase=PHASE_POST_FIX,
            forward_cmd=rec.command,
            pending_instr="",
            clear_instr=(
                "Run the post-fix command verbatim — review PASS, "
                "0 findings, attest no-fix path."
            ),
            lifecycle_flags=lifecycle_flags,
        )
    else:
        # Findings>0: RECOMMENDED_CHOICE_ACCEPT is policy-excluded even
        # when user_choices_for_transition allows it structurally (no fix
        # cycle yet). Bypassing review with raw accept is forbidden.
        policy_excluded = list(rec.excluded)
        if RECOMMENDED_CHOICE_ACCEPT not in policy_excluded:
            policy_excluded.append(RECOMMENDED_CHOICE_ACCEPT)
        policy_enum = [c for c in rec.enum if c not in policy_excluded]
        route_with_ack(
            payload, ctx,
            forward_phase=PHASE_POST_FIX,
            pending_instr="",
            clear_instr=(
                f"post-review reported {findings_count} finding(s); "
                "pick a `--user-choice` from `next_options.user_choice_enum` "
                f"(recommended: {rec.recommended})."
            ),
            lifecycle_flags=lifecycle_flags,
            next_options=NextOptions(
                command_template=rec.command,
                user_choice_enum=tuple(policy_enum),
                user_choice_recommended=rec.recommended,
                user_choice_excluded=tuple(policy_excluded),
                rationale=rec.rationale,
            ),
        )

    output.success(
        payload,
        f"Acknowledged {payload.get('cleared_calls', 0)} pending tool call(s)",
    )


@dataclass
class AckCallsInput(PhaseInput):
    """Typed input for the ``ack-calls`` phase.

    Lifecycle fields (``category``, ``target_name``, ``project_path``,
    ``parent_todo``, ``gate_id``) live on the common parent parser and
    are omitted here; the XOR-pairing invariant is inexpressible on
    the ack-phase Input rather than enforced by an exemption set.
    """


@phase(
    name=PHASE_ACK_CALLS,
    emits=frozenset(),
    help="Clear pending_tool_calls from the gate session",
    description=__doc__,
)
class AckCallsPhase(Phase):
    """Ack-flavoured phase — clears pending_tool_calls after the
    agent executes them. No phase-specific flags; no graph
    transition (ack phases are injected by other phases'
    ``required_tool_calls``).
    """

    Input = AckCallsInput

    def handle(self, args: argparse.Namespace) -> None:
        handle_ack_calls(args)
