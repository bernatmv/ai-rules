"""Pipeline post-fix phase: refresh line counts, update quality artifact."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

from sdd_core import output
from sdd_core.paths import doc_dir_path
from sdd_core.prompts import (
    PIPELINE_INSTRUCTION_CLEAR,
    PIPELINE_INSTRUCTION_PENDING,
    render_pipeline_instruction,
)
from review_quality.staleness import is_doc_stale, check_docs_staleness, set_doc_field
from review_quality.gate_session import (
    write_session, advance_gate, record_user_accept,
    set_phase_snapshot,
    phase_cache_key, hash_quality_artifact,
    read_session,
)
from review_quality.todo_lifecycle import build_cycle_todos, cycle_todo_id
from review_quality.constants import (
    GateState, TodoStatus, DEFAULT_MAX_FIX_CYCLES, USER_CHOICE_ALLOWED,
    user_choices_for_transition, SCOPE_FINAL, SCOPE_PER_DOCUMENT,
    RECOMMENDED_CHOICE_DEFER_EXTERNAL,
)
from sdd_core import review_quality_schema as _rq_schema

from ..phase_kit import Phase, PhaseContext, PhaseInput, phase
from ..snapshots import PostFixSnapshot
from .._routing import (
    build_phase_chain, maybe_append_ack_calls, replay_snapshot, route_with_ack,
)
from ..transitions import phase_key
from . import (
    attach_todo_calls, persist_pending_calls, phase_entry_guard,
    count_effective_lines, build_phase_cmd, build_prompt_cmd,
    read_artifact_score, load_quality_data, quality_file_path,
)
from .constants import (
    PHASE_ACK_CALLS, PHASE_CHECK_REVALIDATION, PHASE_POST_FIX,
    PHASE_POST_REVIEW, PHASE_PRE_APPROVAL, POST_FIX_CLEAN_ADVANCE_LABEL,
    TRIVIAL_ADVANCE_INSTRUCTION,
)
from .common_validators import (
    require_parent_todo_pair as _require_parent_todo_pair,
)
from .update_launch import UpdateLaunchInput, _handle_update_launch


# Sentinel re-exported from review_quality.constants so callers can keep
# importing it from this module's surface; the constant lives in
# review_quality so every consumer reads the same string.
from review_quality.constants import (  # noqa: E402  (re-export for callers)
    USER_CHOICE_RECOMMENDED_SENTINEL,
)


# --user-choice value: operator accepts the current state and advances to pre-approval.
USER_CHOICE_ACCEPT = "accept"
# --user-choice value: operator opts out of the fix cycle (only legal at scope=per-document).
USER_CHOICE_SKIP = "skip"
# --user-choice value: operator advances without remediation; clean-advance chain candidate.
USER_CHOICE_PROCEED = "proceed"
# Excluded option label when re-review is no longer fruitful (max cycles reached).
USER_CHOICE_RE_REVIEW = "re_review"
# Sentinel returned by the snapshot probe when no PostReviewSnapshot exists; callers treat as unknown.
ACTIONABLE_COUNT_UNKNOWN = -1
# Trigger value for the zero-actionable + accept fast-fold; matches the post-review snapshot count.
ACTIONABLE_COUNT_ZERO = 0


def _handle_post_fix_update_mode(
    ctx: PhaseContext, inp: "PostFixInput",
) -> None:
    """Replay the update-mode checklist after a fix lands.

    Returns the same top-level keys :mod:`pipeline_phases.update_launch`
    emits so consumer contracts (TodoWrite payload, ``phase_commands``,
    ``next_action_command`` chain) are byte-identical across the
    ``update-launch`` → ``post-fix`` re-entry boundary.
    """
    relay_inp = UpdateLaunchInput(
        doc_list=inp.doc_list,
        workflow_mode=inp.workflow_mode,
        parent_todo=inp.parent_todo,
        gate_id=inp.gate_id,
        category=ctx.category,
        target_name=ctx.target_name,
    )
    _handle_update_launch(ctx, relay_inp)


# Instruction templates live in `prompt-registry.json` under
# `pipeline-instruction-pending` / `pipeline-instruction-clear`
# (scenario ``post_fix``).


def _post_fix_cache_key(
    session: dict, ctx: PhaseContext, inp: "PostFixInput",
) -> str:
    cached = session.get("launch_args_cache") or {}
    gate = session.get("review_gate") or {}
    return phase_cache_key(
        phase="post-fix",
        artifact_hash=hash_quality_artifact(ctx.category, ctx.target_name, ctx.project_path),
        scope=gate.get("review_scope") or cached.get("scope", SCOPE_PER_DOCUMENT),
        fix_cycle=int(inp.fix_cycle or 0),
        doc_list=inp.doc_list or "",
    )


def _maybe_replay_post_fix(
    session: dict, ctx: PhaseContext, inp: "PostFixInput",
) -> bool:
    """Thin wrapper — see :func:`replay_snapshot` for the replay contract."""
    return replay_snapshot(
        session, ctx,
        phase="post-fix",
        expected_key=_post_fix_cache_key(session, ctx, inp),
        success_message="post-fix replay (cached, no state change)",
        cls=PostFixSnapshot,
    )


def _resolve_recommended_user_choice(
    *, session: dict, ctx: PhaseContext, inp: "PostFixInput",
) -> str:
    """Translate the ``recommended`` sentinel into the canonical verb.

    Reads the cached ``PostReviewSnapshot`` to recover the authoritative
    findings count and gate state, then composes the recommendation via
    :func:`build_post_fix_command_with_recommended`. Errors out with a
    re-run-post-review literal when the snapshot is missing.
    """
    from review.snapshots import PostReviewSnapshot
    from review_quality.gate_session import get_phase_snapshot
    from sdd_core.command_templates import (
        build_post_fix_command_with_recommended,
    )
    snap = get_phase_snapshot(session, PHASE_POST_REVIEW, cls=PostReviewSnapshot)
    if snap is None:
        rerun_cmd = build_phase_cmd(
            PHASE_POST_REVIEW,
            project_path=ctx.project_path,
            category=ctx.category,
            target_name=ctx.target_name,
            lifecycle_flags=(
                f" --parent-todo {ctx.parent_todo} --gate-id {ctx.gate_id}"
                if ctx.parent_todo and ctx.gate_id
                else ""
            ),
        )
        output.recoverable_miss(
            {"reason": "user_choice_recommended_requires_snapshot"},
            "--user-choice recommended requires a post-review snapshot",
            next_action_command_sequence=rerun_cmd,
            problems=[
                "--user-choice recommended requires a post-review snapshot",
            ],
            hint=(
                "Run --phase post-review first to populate "
                "phase_commands.post_fix.user_choice_recommended — "
                "execute next_action_command_sequence, then retry."
            ),
        )
    cached = session.get("launch_args_cache") or {}
    gate = session.get("review_gate") or {}
    findings_count = int(getattr(snap, "actionable_findings", 0) or 0)
    fix_cycle = int(gate.get("fix_cycle", 0) or 0)
    scope = gate.get("review_scope") or cached.get("scope", SCOPE_PER_DOCUMENT)
    rec = build_post_fix_command_with_recommended(
        category=ctx.category,
        target_name=ctx.target_name,
        project_path=cached.get("project_path", ctx.project_path) or "",
        doc_list=cached.get("doc_list", "") or "",
        fix_cycle=fix_cycle,
        max_cycles=int(gate.get("max_cycles", 0) or 0),
        scope=scope,
        findings_count=findings_count,
        parent_todo=ctx.parent_todo or "",
        gate_id=ctx.gate_id or "",
    )
    return rec.recommended


def _post_review_actionable_count(session: dict) -> int:
    """Read the authoritative actionable finding count from the
    persisted ``PostReviewSnapshot`` for the trivial-advance fast-path
    predicate.

    Returns ``-1`` when the snapshot is missing — callers treat that as
    "unknown count, take the slow path" so the fast path is opt-in by
    construction. Function-scope imports avoid a module-load cycle with
    :mod:`review.snapshots` → :mod:`review.pipeline_phases`.
    """
    from review.snapshots import PostReviewSnapshot
    from review_quality.gate_session import get_phase_snapshot
    snap = get_phase_snapshot(
        session, PHASE_POST_REVIEW, cls=PostReviewSnapshot,
    )
    if snap is None:
        return ACTIONABLE_COUNT_UNKNOWN
    return int(getattr(snap, "actionable_findings", 0) or 0)


def _fold_defer_to_pre_approval(
    ctx: PhaseContext, inp: "PostFixInput", session: dict,
) -> None:
    """Advance the gate when every finding routes through an external workflow.

    Refreshes line counts (so the artifact stays in sync), records the
    deferral on ``phase_history`` so the next session can see who
    deferred and why, advances the gate to ``pre-approval`` WITHOUT
    incrementing ``fix_cycle`` (the budget is preserved for follow-up
    in-band fixes), then dispatches the pre-approval emitter directly.
    Mirrors :func:`_fast_fold_to_pre_approval` so the operator sees the
    same single-envelope shape both fast paths emit.
    """
    spec_name = ctx.target_name
    category = ctx.category
    project_path = ctx.project_path

    doc_list = [d.strip() for d in inp.doc_list.split(",") if d.strip()]
    doc_directory = doc_dir_path(category, spec_name, project_path)
    q_path = quality_file_path(category, spec_name, project_path)
    quality_data = load_quality_data(category, spec_name, project_path) or {}

    for doc in doc_list:
        doc_path = os.path.join(doc_directory, doc)
        if not os.path.isfile(doc_path):
            continue
        set_doc_field(quality_data, doc, "line_count", count_effective_lines(doc_path))

    if quality_data and os.path.isfile(q_path):
        output.atomic_write_json(q_path, quality_data)

    # Record the deferral on the canonical artifact's phase_history so a
    # later session can see "fix-loop deferred to external workflow" as
    # an immutable row alongside approve / reject events.
    try:
        canonical_doc = _rq_schema.load(q_path)
    except (FileNotFoundError, ValueError, OSError):
        canonical_doc = None
    if isinstance(canonical_doc, dict):
        from sdd_core.time import ts_now as _ts_now
        _rq_schema.append_phase_history(canonical_doc, {
            "phase": "defer_external",
            "user_choice": RECOMMENDED_CHOICE_DEFER_EXTERNAL,
            "fix_cycle": int(inp.fix_cycle or 0),
            "doc_list": inp.doc_list,
            "recorded_at": _ts_now(),
        })
        try:
            _rq_schema.atomic_write(q_path, canonical_doc)
        except OSError:
            pass

    # Advance the gate but DO NOT mutate ``fix_cycle`` — the budget
    # carries forward so a subsequent in-band fix loop after the
    # external workflow runs is not penalised by this defer.
    session = advance_gate(session, required_next_phase=PHASE_PRE_APPROVAL)
    write_session(category, spec_name, session, project_path)

    from .pre_approval import _handle_pre_approval, PreApprovalInput
    _handle_pre_approval(
        ctx,
        PreApprovalInput(
            doc_list=inp.doc_list,
            parent_todo=ctx.parent_todo or None,
            gate_id=ctx.gate_id or None,
        ),
    )


def _fast_fold_to_pre_approval(
    ctx: PhaseContext, inp: "PostFixInput", session: dict,
) -> None:
    """Skip the post-fix envelope when nothing needs fixing.

    Refreshes line counts (so the quality artifact stays in sync with
    on-disk doc lengths), records the user-accept marker on the session,
    advances the gate to ``pre-approval``, persists, then dispatches the
    pre-approval emitter directly. The agent sees one envelope where
    the legacy three-step path emitted three.
    """
    spec_name = ctx.target_name
    category = ctx.category
    project_path = ctx.project_path

    doc_list = [d.strip() for d in inp.doc_list.split(",") if d.strip()]
    doc_directory = doc_dir_path(category, spec_name, project_path)
    q_path = quality_file_path(category, spec_name, project_path)
    quality_data = load_quality_data(category, spec_name, project_path) or {}

    for doc in doc_list:
        doc_path = os.path.join(doc_directory, doc)
        if not os.path.isfile(doc_path):
            continue
        set_doc_field(quality_data, doc, "line_count", count_effective_lines(doc_path))

    if quality_data and os.path.isfile(q_path):
        output.atomic_write_json(q_path, quality_data)

    session = record_user_accept(session)
    session = advance_gate(session, required_next_phase=PHASE_PRE_APPROVAL)
    write_session(category, spec_name, session, project_path)

    from .pre_approval import _handle_pre_approval, PreApprovalInput
    _handle_pre_approval(
        ctx,
        PreApprovalInput(
            doc_list=inp.doc_list,
            parent_todo=ctx.parent_todo or None,
            gate_id=ctx.gate_id or None,
        ),
    )


def _handle_post_fix(
    ctx: PhaseContext, inp: "PostFixInput",
) -> None:
    """After fixes applied: refresh line counts, update quality artifact, return merged prompt.

    Lifecycle fields arrive via :class:`PhaseContext`; phase-specific
    flags via :class:`PostFixInput`. When ``workflow_mode`` is
    ``"update"``, refreshes the ``update-mode.default.v1`` checklist
    instead of the creation-mode review-gate checklist — same envelope
    keys, different checklist source.
    """
    if inp.workflow_mode == "update":
        _handle_post_fix_update_mode(ctx, inp)
        return

    spec_name = ctx.target_name
    category = ctx.category
    project_path = ctx.project_path

    # Idempotency replay must run before ``phase_entry_guard`` so that a
    # truncation-retry does not trip the sequence-violation block on the
    # advanced required_next_phase.
    replay_session = read_session(category, spec_name, project_path)
    if inp.user_choice == USER_CHOICE_RECOMMENDED_SENTINEL:
        inp.user_choice = _resolve_recommended_user_choice(
            session=replay_session, ctx=ctx, inp=inp,
        )
    if _maybe_replay_post_fix(replay_session, ctx, inp):
        return

    # When the fix cycle was already auto-closed by a clean re-review
    # in ``post_review``, a subsequent ``post-fix --user-choice proceed``
    # is a replay-tolerant no-op rather than a sequence violation.
    # Short-circuit with a stable envelope so the manual recovery path
    # stays unblocked.
    replay_gate = replay_session.get("review_gate") or {}
    if (
        replay_gate.get("fix_cycle_terminated_by") == "clean_re_review"
        and int(replay_gate.get("fix_cycle", 0) or 0) == 0
    ):
        output.success(
            {
                "status": "noop",
                "reason": "fix_cycle_already_auto_closed",
                "fix_cycle_terminated_by": "clean_re_review",
            },
            "post-fix no-op: fix cycle auto-closed by clean re-review",
        )
        return

    session, blocked = phase_entry_guard(category, spec_name, project_path, "post-fix")
    if blocked:
        output.success(blocked, blocked["reason"])
        return

    # Defer-to-external-workflow fold: when every actionable finding
    # roots outside the doc, fixing in-doc cannot help — surface the
    # remediation literal at post-review and advance the gate here
    # without consuming budget. Single-envelope path mirrors the
    # zero-findings accept fast-fold.
    if inp.user_choice == RECOMMENDED_CHOICE_DEFER_EXTERNAL:
        _fold_defer_to_pre_approval(ctx, inp, session)
        return

    # Zero-findings + accept fast-fold: when the prior post-review
    # snapshot reports zero actionable findings and the user accepted,
    # ack-calls → post-fix → pre-approval is three round-trips for a
    # no-op. Refresh line counts, record acceptance, then dispatch
    # straight to the pre-approval emitter so a single tick lands the
    # agent on the approval prompt envelope.
    if (
        inp.user_choice == USER_CHOICE_ACCEPT
        and _post_review_actionable_count(session) == ACTIONABLE_COUNT_ZERO
    ):
        _fast_fold_to_pre_approval(ctx, inp, session)
        return

    doc_list = [d.strip() for d in inp.doc_list.split(",") if d.strip()]
    fix_cycle = inp.fix_cycle
    max_cycles = inp.max_cycles

    doc_directory = doc_dir_path(category, spec_name, project_path)
    q_path = quality_file_path(category, spec_name, project_path)

    updated_counts = {}
    quality_data = load_quality_data(category, spec_name, project_path) or {}

    for doc in doc_list:
        doc_path = os.path.join(doc_directory, doc)
        if not os.path.isfile(doc_path):
            continue
        count = count_effective_lines(doc_path)
        updated_counts[doc] = count
        set_doc_field(quality_data, doc, "line_count", count)

    stale_docs, _ = check_docs_staleness(doc_list, doc_directory, quality_data)
    any_modified_after_review = len(stale_docs) > 0

    quality_refreshed = False
    if quality_data and os.path.isfile(q_path):
        output.atomic_write_json(q_path, quality_data)
        quality_refreshed = True

    parent_todo = ctx.parent_todo or None
    warnings = []

    gate = session.get("review_gate") or {}

    gate["fix_cycle"] = fix_cycle
    gate["current_state"] = GateState.RE_VALIDATE

    if parent_todo:
        expected_apply = cycle_todo_id(fix_cycle, "apply")
        actual_active = {t["id"]: t.get("status") for t in gate.get("active_todos", [])}

        if actual_active and expected_apply in actual_active:
            if actual_active[expected_apply] != TodoStatus.IN_PROGRESS:
                warnings.append(
                    f"active_todos drift: expected {expected_apply}=in_progress, "
                    f"got {actual_active[expected_apply]}"
                )

        review_scope = gate.get("review_scope", SCOPE_PER_DOCUMENT)
        cycle_todos = build_cycle_todos(fix_cycle, review_scope=review_scope)
        if not cycle_todos:
            raise RuntimeError(
                f"No cycle TODOs generated for scope {category!r}; "
                "review_scope is invalid (programmer error — the gate "
                "must validate scope before scheduling cycle TODOs)."
            )
        apply_todo, validate_todo, *rest = cycle_todos
        apply_todo["status"] = TodoStatus.COMPLETED
        validate_todo["status"] = TodoStatus.IN_PROGRESS
        gate["active_todos"] = cycle_todos

    user_choice = inp.user_choice
    can_continue = fix_cycle < max_cycles
    session = advance_gate(
        session,
        last_completed_phase=PHASE_POST_FIX,
        last_completed_user_choice=user_choice,
    )
    gate = session.get("review_gate") or {}

    # Guard against structural violations that should never reach
    # post-fix: ``skip`` is meaningless at ``scope=final`` (already on
    # the last step). The ``post-review`` envelope advertises the full
    # excluded set via ``user_choices_for_transition``.
    _cached = session.get("launch_args_cache") or {}
    review_scope = gate.get("review_scope") or _cached.get("scope", SCOPE_PER_DOCUMENT)
    if user_choice == USER_CHOICE_SKIP and review_scope == SCOPE_FINAL:
        _, policy_excluded = user_choices_for_transition(
            scope=review_scope,
            fix_cycle=int(fix_cycle or 0),
            findings_count=1,
        )
        recovery_cmd = build_phase_cmd(
            PHASE_POST_REVIEW,
            project_path=project_path,
            category=category,
            target_name=spec_name,
            lifecycle_flags=(
                f" --parent-todo {ctx.parent_todo} --gate-id {ctx.gate_id}"
                if ctx.parent_todo and ctx.gate_id
                else ""
            ),
        )
        problems = [
            f"user_choice {user_choice!r} is excluded at this transition.",
            (
                f"Excluded set for (scope={review_scope}, "
                f"fix_cycle={fix_cycle}): {list(policy_excluded)}."
            ),
        ]
        output.recoverable_miss(
            {"reason": "user_choice_excluded_at_transition"},
            f"user_choice '{user_choice}' is excluded at this transition",
            next_action_command_sequence=recovery_cmd,
            problems=problems,
            hint=(
                f"{problems[0]} Pick a value from "
                "phase_commands.post_fix_user_choices emitted on the most "
                "recent post-review envelope — execute "
                "next_action_command_sequence, then retry."
            ),
        )

    if user_choice == USER_CHOICE_ACCEPT:
        session = record_user_accept(session)
        session = advance_gate(session, required_next_phase=PHASE_PRE_APPROVAL)
    elif not can_continue:
        session = advance_gate(session,
            current_state=GateState.MAX_CYCLES_EXHAUSTED,
            terminal_state=GateState.NEEDS_WORK,
            terminal_reason="Max fix cycles reached",
            required_next_phase=PHASE_PRE_APPROVAL,
        )
    else:
        session = advance_gate(session,
            required_next_phase=PHASE_CHECK_REVALIDATION,
        )

    write_session(category, spec_name, session, project_path)

    # The fix-loop-continue prompt must only offer options the pipeline
    # will honour. When the cycle budget is exhausted, re-review is a
    # no-op and accept would route silently around pre-approval, so the
    # menu collapses to ``revise``.
    exclude_opts: list[str] = []
    if any_modified_after_review:
        exclude_opts.append(USER_CHOICE_ACCEPT)
    if not can_continue:
        if USER_CHOICE_ACCEPT not in exclude_opts:
            exclude_opts.append(USER_CHOICE_ACCEPT)
        exclude_opts.append(USER_CHOICE_RE_REVIEW)

    prompt_command = build_prompt_cmd(
        "fix-loop-continue",
        f"fix_cycle={fix_cycle} max_fix_cycles={max_cycles}",
        exclude_opts=exclude_opts,
    )

    cached = session.get("launch_args_cache", {})
    # ``gate-id`` is caller-owned: when both lifecycle flags arrive on
    # the context, rebuild from them so the cached launch-time id can
    # not silently overwrite the caller's value.
    if ctx.gate_id and ctx.parent_todo:
        lf = f" --parent-todo {ctx.parent_todo} --gate-id {ctx.gate_id}"
    else:
        lf = cached.get('lifecycle_flags', '')
    pre_approval_cmd = build_phase_cmd(
        PHASE_PRE_APPROVAL,
        project_path=cached.get('project_path', project_path),
        category=category,
        target_name=spec_name,
        extra_args=f'--doc-list "{inp.doc_list}"',
        lifecycle_flags=lf,
    )
    check_revalidation_cmd = build_phase_cmd(
        PHASE_CHECK_REVALIDATION,
        project_path=cached.get('project_path', project_path),
        category=category,
        target_name=spec_name,
        extra_args=f'--doc "<doc_name>" --fix-cycle {fix_cycle} --max-cycles {max_cycles}',
        lifecycle_flags=lf,
    )

    # Trivial-advance fast path. When the operator accepted on a
    # post-review whose authoritative ``actionable_findings`` was zero,
    # the gate is already at pre-approval (line above) and ack-calls /
    # check-revalidation cannot move it further. Skip both round-trips
    # and route directly so one ``pipeline-tick`` lands the agent on
    # pre-approval. The strict precondition is
    # ``actionable_count == 0`` per the post-review snapshot — read it
    # here so the fast path stays tied to the authoritative count, not
    # to the agent-supplied flags.
    accept_zero_actionable = (
        user_choice == USER_CHOICE_ACCEPT
        and _post_review_actionable_count(session) == ACTIONABLE_COUNT_ZERO
    )
    if accept_zero_actionable:
        forward = (PHASE_PRE_APPROVAL, pre_approval_cmd)
        other = (PHASE_CHECK_REVALIDATION, check_revalidation_cmd)
        msg_suffix = "accept, "
    elif not can_continue:
        forward = (PHASE_PRE_APPROVAL, pre_approval_cmd)
        other = (PHASE_CHECK_REVALIDATION, check_revalidation_cmd)
        msg_suffix = "max cycles reached, "
    else:
        forward = (PHASE_CHECK_REVALIDATION, check_revalidation_cmd)
        other = (PHASE_PRE_APPROVAL, pre_approval_cmd)
        msg_suffix = ""
    forward_phase, forward_cmd = forward
    other_phase, other_cmd = other
    forward_key = phase_key(forward_phase)

    artifact_score = read_artifact_score(category, spec_name, project_path, data=quality_data)

    result = {
        "updated_counts": updated_counts,
        "quality_artifact_refreshed": quality_refreshed,
        "artifact_score": artifact_score,
        "re_review_required": any_modified_after_review,
        "fix_cycle": fix_cycle,
        "max_cycles": max_cycles,
        "can_continue": can_continue,
        "next_action": (
            "present_post_fix_prompt" if not can_continue else "check_revalidation"
        ),
        "prompt_command": prompt_command,
        "post_fix_user_choices": list(USER_CHOICE_ALLOWED),
        "post_fix_user_choices_excluded": exclude_opts,
        # Informative forward-look: surface the phase the gate routes
        # into AFTER the immediate next step lands. Pure preview — the
        # agent still dispatches off ``next_action_command``; this is a
        # name to set expectations, not a peer command listing.
        "after_post_fix_next_phase": forward_phase,
    }

    if parent_todo and not accept_zero_actionable:
        active = gate.get("active_todos", [])
        todos = [
            {"id": parent_todo, "content": f"Review gate: {parent_todo}",
             "status": TodoStatus.IN_PROGRESS},
            *active,
        ]
        attach_todo_calls(result, {
            "todo_write_payload": {"todos": todos, "merge": True},
        })
        # Append the ack-calls Shell entry so the agent always has the
        # unblock command next to the TodoWrite (single source of truth,
        # same helper ``launch.py`` / ``post_review.py`` use).
        maybe_append_ack_calls(result, ctx, lifecycle_flags=lf)
        persist_pending_calls(gate, result)
        write_session(category, spec_name, session, project_path)

    # Route through the shared helper — single source of truth for
    # ack-aware next_phase / next_action_command. The phase-graph in
    # :data:`review.transitions.TRANSITIONS` is the canonical source of
    # truth for "what comes after that?"; operators read it via
    # ``pipeline-tick.py --describe-phase-graph`` instead of an
    # alternative-branch peer listing on every envelope.
    pending_instr = render_pipeline_instruction(
        PIPELINE_INSTRUCTION_PENDING, "post_fix", forward_key=forward_key,
    )
    clear_instr = render_pipeline_instruction(
        PIPELINE_INSTRUCTION_CLEAR, "post_fix", forward_key=forward_key,
    )
    route_with_ack(
        result, ctx,
        forward_phase=forward_phase,
        forward_cmd=forward_cmd,
        pending_instr=pending_instr,
        clear_instr=clear_instr,
        lifecycle_flags=lf,
    )

    # Clean-advance chain. When user_choice is the no-op "proceed" and
    # the document has no outstanding findings, the agent's path is
    # ack-calls → check-revalidation → pre-approval. Emit a
    # ``next_action_command_sequence`` so the agent runs one Bash turn
    # and the state machine advances three phases — three observable
    # transitions become one literal command. ``next_action_command``
    # still points at the first chain element so agents on the old
    # protocol recover in three turns and agents on the new protocol
    # recover in one. No flag-day cutover.
    if (
        user_choice == USER_CHOICE_PROCEED
        and not any_modified_after_review
        and can_continue
    ):
        from .._routing import build_trivial_advance_chain
        # Build the chain from local command variables instead of
        # reading the alternative peer back off ``result``: the
        # phase-graph already encodes the order.
        chain_phase_cmds = {
            "ack_calls": result.get("phase_commands", {}).get("ack_calls", ""),
            "check_revalidation": check_revalidation_cmd,
            "pre_approval": pre_approval_cmd,
        }
        chain_pair = build_trivial_advance_chain(
            chain_phase_cmds, POST_FIX_CLEAN_ADVANCE_LABEL,
        )
        if chain_pair is not None:
            chain, label = chain_pair
            result["next_action_command_sequence"] = chain
            result["next_action_command_sequence_label"] = label
            result["instruction"] = TRIVIAL_ADVANCE_INSTRUCTION

    if warnings:
        result["warnings"] = warnings

    # Persist the idempotency snapshot now that routing is settled. Store
    # both forward + sibling so replay reconstructs ``phase_commands``
    # identically. The template variables are reused verbatim from the
    # live call above — single source of truth.
    snapshot_required = [dict(c) for c in (result.get("required_tool_calls") or [])]
    set_phase_snapshot(session, PostFixSnapshot(
        key=_post_fix_cache_key(session, ctx, inp),
        updated_counts=updated_counts,
        quality_artifact_refreshed=quality_refreshed,
        artifact_score=artifact_score,
        re_review_required=any_modified_after_review,
        fix_cycle=fix_cycle,
        max_cycles=max_cycles,
        can_continue=can_continue,
        next_action=result["next_action"],
        prompt_command=prompt_command,
        post_fix_user_choices_excluded=exclude_opts,
        forward_phase=forward_phase,
        forward_cmd=forward_cmd,
        other_phase=other_phase,
        other_cmd=other_cmd,
        pending_instr=pending_instr,
        clear_instr=clear_instr,
        lifecycle_flags=lf,
        required_tool_calls=snapshot_required,
        todo_write_payload=result.get("todo_write_payload"),
    ))
    write_session(category, spec_name, session, project_path)

    output.success(
        result,
        f"Post-fix refresh complete — {msg_suffix}{len(updated_counts)} doc(s) updated",
    )


from review_quality.constants import WORKFLOW_MODES as _POST_FIX_WORKFLOW_MODES  # noqa: E402


@dataclass
class PostFixInput(PhaseInput):
    """Typed input for the ``post-fix`` phase.

    The XOR-pairing invariant lives on :meth:`__post_init__`.
    Lifecycle fields mirror the common parent parser so the validator
    has the values it needs; :meth:`Phase._attach_input_flags` skips
    them so they are not re-exposed as CLI flags.
    """

    doc_list: str = field(
        default=None, metadata={"help": "Comma-separated document list"},
    )
    fix_cycle: int = field(
        default=0, metadata={"help": "Current fix cycle"},
    )
    max_cycles: int = field(
        default=DEFAULT_MAX_FIX_CYCLES, metadata={"help": "Max cycles"},
    )
    user_choice: str = field(
        default=None,
        metadata={
            "help": (
                "User's fix-decision choice. Pass `recommended` to use "
                "the value the post-review envelope already chose; the "
                "shim resolves it server-side."
            ),
            # Canonical vocabulary lives in ``review_quality.constants``
            # so the ``post-review`` envelope and this argparse share
            # one source of truth. ``recommended`` is the sentinel that
            # resolves server-side via the cached gate snapshot.
            "choices": tuple(USER_CHOICE_ALLOWED) + (USER_CHOICE_RECOMMENDED_SENTINEL,),
        },
    )
    workflow_mode: str = field(
        default="create",
        metadata={
            "help": (
                "Workflow mode. ``update`` refreshes the "
                "update-mode.default.v1 checklist instead of the "
                "creation-mode review-gate checklist."
            ),
            "choices": _POST_FIX_WORKFLOW_MODES,
        },
    )
    parent_todo: Optional[str] = None
    gate_id: Optional[str] = None

    def __post_init__(self) -> None:
        _require_parent_todo_pair(self.parent_todo, self.gate_id)


@phase(
    name="post-fix",
    emits=frozenset({PHASE_CHECK_REVALIDATION, PHASE_PRE_APPROVAL}),
    help="Refresh line counts, update quality artifact, return merged prompt",
    description=__doc__,
)
class PostFixPhase(Phase):
    """Post-fix branch — refreshes line counts and quality artifact
    after agent fixes, then routes to check-revalidation or
    pre-approval.
    """

    Input = PostFixInput

    def handle(self, ctx: PhaseContext, inp: PostFixInput) -> None:
        _handle_post_fix(ctx, inp)
