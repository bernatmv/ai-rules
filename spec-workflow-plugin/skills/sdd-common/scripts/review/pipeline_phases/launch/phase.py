"""Launch phase orchestrator.

Owns ``_handle_launch`` (the orchestration body that wires the
precondition gate, prompt assembly, session bootstrap and result
assembly into the final envelope). Sub-helpers are imported from
:mod:`.preconditions`, :mod:`.prompt`, :mod:`.session_setup`, and
:mod:`.result_assembly`. The :class:`LaunchInput` /
:class:`LaunchPhase` dataclass + registration live in
:mod:`.dataclass`.
"""
from __future__ import annotations

import os

from sdd_core import output
from sdd_core.command_templates import (
    build_pipeline_tick_discard_command,
    build_template_resolve_commands,
    promote_post_fix_phase_command,
)
from sdd_core.prompts import (
    PIPELINE_INSTRUCTION_CLEAR,
    PIPELINE_INSTRUCTION_PENDING,
    render_pipeline_instruction,
)
from review_quality.gate_session import (
    GATE_LAUNCH_ARGS_CACHE,
    GATE_REENTRY_COUNT,
    advance_gate,
    read_session,
    session_path,
    write_session,
)

from ...phase_kit import PhaseContext
from ..._routing import route_with_ack
from .. import persist_pending_calls
from ..constants import (
    ADVISORY_CODE_ABANDONED_PRIOR_GATE,
    ADVISORY_LEVEL_ERROR,
    KEY_ADVISORIES,
    PHASE_POST_REVIEW,
)
from .. import launch_preconditions as _launch_pre
from ..resolvers import resolve_staging_path

from .preconditions import (
    _resolve_review_type,
    _run_launch_preconditions,
    _run_requirements_pre_check,
)
from .prompt import (
    GATE_PROMPT_KEY,
    _build_gate_prompt,
    _build_sub_agent_prompt,
    _classify_prompt_change,
    _compute_doc_list_sha,
    _read_prior_launch_shas,
)
from .result_assembly import (
    OUTCOME_PRECONDITIONS_UNMET,
    OUTCOME_READY,
    _apply_prompt_change_status,
    _apply_warn_payload,
    _build_launch_result,
    _emit_reentry_todos_if_needed,
)
from .session_setup import (
    _build_command_maps,
    _init_session_and_cache,
    _launch_time_post_fix_user_choices,
    _maybe_enforce_single_doc_stop_gate,
    _validate_prompt_registry,
)


# ``post_fix_user_choices_source`` — names which transition emitted
# the user-choice list on a given envelope. The agent dispatches on
# this field instead of memorising a "most-recent-envelope-wins"
# precedence rule.
POST_FIX_USER_CHOICES_SOURCE_LAUNCH = "launch_baseline"
POST_FIX_USER_CHOICES_SOURCE_POST_REVIEW = "post_review_actual"


# ---------------------------------------------------------------------------
# Cache key constants for prior-launch SHA persistence
# ---------------------------------------------------------------------------

_CACHE_LAST_PROMPT_SHA = "last_prompt_sha"
_CACHE_LAST_DOC_SHA = "last_doc_sha"


def _check_abandoned_prior_gate(ctx: PhaseContext, gate_id: str) -> None:
    """Hard-block when a non-terminal prior gate's gate_id disagrees.

    Without this check, ``init_session`` (under ``workflow_mode=update``)
    silently resets the prior gate when the caller supplies a different
    ``--gate-id`` — losing pending fix-loop state and any staged scores.
    The advisory surfaces the conflict and points the operator at the
    canonical recovery (``--phase discard --gate-id <prior>``) so the
    drop is explicit, auditable, and tied to a single literal command.

    No-ops when:

    * no session file exists (fresh workflow — nothing to abandon),
    * the recorded gate_id matches the caller (normal resume),
    * the recorded gate is terminal (already settled — safe to overwrite),
    * the caller passes no gate_id (older clients that have not migrated
      to the lifecycle-flag contract).
    """
    if not gate_id:
        return
    if not os.path.isfile(
        session_path(ctx.category, ctx.target_name, ctx.project_path),
    ):
        return
    session = read_session(
        ctx.category, ctx.target_name, ctx.project_path,
        quiet_missing=True,
    )
    gate = session.get("review_gate") or {}
    prior_gate_id = (gate.get("gate_id") or "").strip()
    if not prior_gate_id or prior_gate_id == gate_id:
        return
    if gate.get("terminal_state"):
        return

    discard_cmd = build_pipeline_tick_discard_command(
        gate_id=prior_gate_id,
        workspace_path=ctx.project_path or ".",
    )
    advisory = output.advisory(
        (
            f"abandoned prior gate {prior_gate_id!r} is non-terminal — "
            f"launch with gate_id={gate_id!r} would drop in-flight "
            "fix-loop state. Discard the prior gate first or re-run "
            "with the matching --gate-id."
        ),
        level=ADVISORY_LEVEL_ERROR,
        code=ADVISORY_CODE_ABANDONED_PRIOR_GATE,
    )
    output.recoverable_miss(
        {
            "outcome": "abandoned_prior_gate",
            "prior_gate_id": prior_gate_id,
            "requested_gate_id": gate_id,
            "next_action_command": discard_cmd,
            KEY_ADVISORIES: [advisory],
        },
        "launch blocked: prior gate not discarded",
        next_action_command_sequence=discard_cmd,
        problems=[
            f"prior gate {prior_gate_id!r} is mid-flight; "
            f"caller requested {gate_id!r}"
        ],
        hint=(
            "Run the discard command (next_action_command) to drop the "
            "prior gate, then retry --phase launch with the new gate-id."
        ),
    )


def _handle_launch(ctx: PhaseContext, inp: "LaunchInput") -> None:
    """Initialize review session, build sub-agent prompt and all pipeline commands.

    Lifecycle values flow through :class:`PhaseContext`; phase-specific
    flags through :class:`LaunchInput`. ``parent_todo_content`` rides
    on the common parent parser and is declared on :class:`LaunchInput`
    so :meth:`Phase._build_input` picks it up from the namespace
    without re-exposing it as a phase-specific CLI flag.
    """
    review_skill = inp.review_skill
    doc_list = inp.doc_list
    scope = inp.scope
    max_fix_cycles = inp.max_fix_cycles
    parent_todo = ctx.parent_todo or None
    gate_id = ctx.gate_id or ""
    lifecycle_flags = f" --parent-todo {parent_todo} --gate-id {gate_id}"

    review_type = _resolve_review_type(review_skill)

    # Hard-block before any session mutation when a non-terminal prior
    # gate disagrees with the caller's gate-id; init_session would
    # otherwise reset the prior gate under workflow_mode=update and
    # lose its fix-loop / staging state silently.
    _check_abandoned_prior_gate(ctx, gate_id)

    # Surface an AskQuestion gate when the previous launch stopped
    # after a single-document approval. Consumes the marker once the
    # agent passes --confirm-continuation so the gate fires only
    # once per early-stop session.
    _maybe_enforce_single_doc_stop_gate(ctx, inp, doc_list)

    warn_payload = _run_launch_preconditions(
        ctx, scope=scope, workflow_mode=inp.workflow_mode,
        gate_id=gate_id,
        review_skill=review_skill, doc_list=doc_list,
    )

    missing_names = {
        entry.get("name")
        for entry in (warn_payload or {}).get("missing_preconditions", [])
        if isinstance(entry, dict)
    }
    pre_launch_sequence = _launch_pre.build_pre_launch_sequence(
        category=ctx.category,
        target_name=ctx.target_name,
        project_path=ctx.project_path,
        gate_id=gate_id,
        scope=scope,
        workflow_mode=inp.workflow_mode,
        missing_names=missing_names,
    )

    pre_check_notes = _run_requirements_pre_check(
        doc_list=doc_list, category=ctx.category,
        spec_name=ctx.target_name, project_path=ctx.project_path,
    )

    # Capture prior-launch hashes BEFORE ``_init_session_and_cache``
    # rebuilds the cache; the comparison feeds ``prompt_change_status``.
    prior_prompt_sha, prior_doc_sha = _read_prior_launch_shas(
        category=ctx.category, target_name=ctx.target_name,
        project_path=ctx.project_path,
    )

    assessment_staging_path = resolve_staging_path(
        ctx.category, ctx.target_name, ctx.project_path,
        gate_id=gate_id,
    )
    sub_agent_prompt, review_skill_path, verification_file = _build_sub_agent_prompt(
        review_skill, ctx, doc_list, review_type, assessment_staging_path,
        scope=scope,
    )

    prompt_commands, phase_commands, re_review_cmds = _build_command_maps(
        ctx.project_path, ctx.category, ctx.target_name, doc_list,
        max_fix_cycles, lifecycle_flags,
    )
    # Surface the launch-time baseline so agents can pre-frame the
    # fix-decision question off the launch envelope. ``post-review``
    # overrides these once a real findings count is known and any
    # doc-edit-driven exclusions (e.g. ``accept`` after edits) apply.
    launch_allowed, launch_excluded = _launch_time_post_fix_user_choices(scope)
    phase_commands["post_fix_user_choices"] = launch_allowed
    phase_commands["post_fix_user_choices_excluded"] = launch_excluded
    # Source marker — agents read this field to know which transition
    # emitted the choices (so the dispatch is "use the value", not
    # "memorise a precedence rule"). ``launch`` always stamps the
    # deterministic baseline; ``post-review`` re-stamps with the
    # state-aware override once findings counts are known.
    phase_commands["post_fix_user_choices_source"] = (
        POST_FIX_USER_CHOICES_SOURCE_LAUNCH
    )
    # Promote phase_commands.post_fix to a discriminated record carrying
    # the literal post-fix command paired with its recommended choice
    # (LSP invariant — readers never see a both-null next step).
    promote_post_fix_phase_command(
        phase_commands,
        category=ctx.category,
        target_name=ctx.target_name,
        project_path=ctx.project_path,
        doc_list=doc_list,
        fix_cycle=0,
        max_cycles=max_fix_cycles,
        scope=scope,
        findings_count=0,
        parent_todo=parent_todo or "",
        gate_id=gate_id,
        lifecycle_flags=lifecycle_flags,
    )
    template_resolve_commands = build_template_resolve_commands(
        doc_list, project_path=ctx.project_path, spec_name=ctx.target_name,
    )
    prompt_registry_advisories = _validate_prompt_registry(prompt_commands)

    session, gate, persisted_cycle = _init_session_and_cache(
        ctx,
        workflow_mode=inp.workflow_mode,
        parent_todo_content=inp.parent_todo_content,
        review_skill=review_skill, doc_list=doc_list, scope=scope,
        lifecycle_flags=lifecycle_flags, max_fix_cycles=max_fix_cycles,
    )

    required_reference_reads = _launch_pre.build_required_reference_reads(
        category=ctx.category,
        review_skill=review_skill,
        project_path=ctx.project_path,
    )
    persisted_reentry = int(gate.get(GATE_REENTRY_COUNT, 0) or 0)

    result = _build_launch_result(
        sub_agent_prompt, review_skill_path, verification_file,
        assessment_staging_path, re_review_cmds, prompt_commands,
        phase_commands, max_fix_cycles, persisted_cycle,
        scope, ctx.category, review_type, doc_list,
        parent_todo=parent_todo,
        required_reference_reads=required_reference_reads,
        reentry_count=persisted_reentry,
    )
    if template_resolve_commands:
        result["template_resolve_commands"] = template_resolve_commands
    if pre_check_notes:
        result["pre_check_notes"] = pre_check_notes
    if pre_launch_sequence:
        result["pre_launch_sequence"] = pre_launch_sequence
    if prompt_registry_advisories:
        result.setdefault(KEY_ADVISORIES, []).extend(prompt_registry_advisories)

    # Cache the emitted prompt hash + reference reads so post-review can
    # compare them against the sub-agent's echoed values (single source
    # of truth for both integrity checks).
    session[GATE_LAUNCH_ARGS_CACHE]["prompt_sha256"] = result["sub_agent_prompt_sha256"]
    session[GATE_LAUNCH_ARGS_CACHE]["required_reference_reads"] = [
        dict(entry) for entry in required_reference_reads
    ]

    # Emit ``prompt_change_status`` only on re-launches — the field is
    # absent on a fresh first launch so consumers can branch on its
    # presence rather than memorising a sentinel string. ``last_*_sha``
    # is persisted into the cache so the *next* launch sees the values
    # this launch emitted.
    curr_prompt_sha = result["sub_agent_prompt_sha256"]
    curr_doc_sha = _compute_doc_list_sha(
        category=ctx.category, target_name=ctx.target_name,
        project_path=ctx.project_path, doc_list=doc_list,
    )
    prompt_change_status = _classify_prompt_change(
        prior_prompt_sha=prior_prompt_sha,
        prior_doc_sha=prior_doc_sha,
        curr_prompt_sha=curr_prompt_sha,
        curr_doc_sha=curr_doc_sha,
    )
    _apply_prompt_change_status(result, prompt_change_status)
    session[GATE_LAUNCH_ARGS_CACHE][_CACHE_LAST_PROMPT_SHA] = curr_prompt_sha
    session[GATE_LAUNCH_ARGS_CACHE][_CACHE_LAST_DOC_SHA] = curr_doc_sha

    # Pre-render the post-review fix-decision prompt onto the launch
    # envelope so the agent reaches the gate boundary without invoking
    # ``util/generate-prompt.py``. ``None`` falls back to the existing
    # markdown path through ``prompt_commands.review_fix_issues``.
    gate_prompt = _build_gate_prompt()
    if gate_prompt is not None:
        result[GATE_PROMPT_KEY] = gate_prompt

    session = advance_gate(session, review_scope=scope, required_next_phase=PHASE_POST_REVIEW)

    # launch is the sole emitter of stale-doc re-entry TODOs;
    # route_with_ack re-points next_action_command to ack-calls when
    # they are attached, so the envelope stays internally consistent.
    from .._envelope import stamp_reentry_metadata
    _emit_reentry_todos_if_needed(result, gate, parent_todo)
    stamp_reentry_metadata(result, gate)
    persist_pending_calls(gate, result)
    pending_instr = render_pipeline_instruction(
        PIPELINE_INSTRUCTION_PENDING, "launch", forward_key="post_review",
    )
    clear_instr = render_pipeline_instruction(
        PIPELINE_INSTRUCTION_CLEAR, "launch", forward_key="post_review",
    )
    # ``route_with_ack`` replaces ``result["phase_commands"]`` wholesale.
    # Phase-graph traversal lives in :data:`review.transitions.TRANSITIONS`
    # and is exposed by ``pipeline-tick.py --describe-phase-graph``;
    # raw alternative-branch peer listings are deliberately omitted here.
    # The post-fix discriminated record + user-choice vocabulary are
    # not "peer commands" — they configure the next user_choice, so
    # they ride on the envelope alongside the ack/forward routing pair.
    launch_metadata = {
        key: cmd for key, cmd in phase_commands.items()
        if key in {
            "post_fix", "post_fix_user_choices",
            "post_fix_user_choices_excluded", "post_fix_user_choices_source",
        }
    }
    route_with_ack(
        result, ctx,
        forward_phase=PHASE_POST_REVIEW,
        forward_cmd=phase_commands["post_review"],
        pending_instr=pending_instr,
        clear_instr=clear_instr,
        lifecycle_flags=lifecycle_flags,
        extra_phase_commands=launch_metadata,
    )

    write_session(ctx.category, ctx.target_name, session, ctx.project_path)

    # Block-first envelope: redact the prompt while preconditions are
    # unmet so an agent cannot dispatch off a stale SHA.
    _apply_warn_payload(result, warn_payload)

    output.success(result, f"Pipeline prepared for {review_skill} ({scope} scope)")
