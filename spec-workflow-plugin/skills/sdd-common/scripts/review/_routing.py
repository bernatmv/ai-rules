"""Routing / snapshot / replay helpers shared by every phase.

Physical home for the ``route_with_ack`` / ``maybe_append_ack_calls``
/ ``replay_snapshot`` implementations. Lives one level up from
:mod:`review.pipeline_phases` so :mod:`review.phase_kit` can import
it at module scope without pulling in the heavy ``pipeline_phases``
barrel (no back-edge to ``pipeline_phases`` at module scope).

Every helper takes a :class:`review.phase_kit.PhaseContext` directly:
routing, persistence, and emission all read from the same typed
shape (``category`` / ``target_name`` / ``project_path`` plus the
lifecycle fields ``gate_id`` / ``parent_todo``).

Function-scope imports of
:func:`review.pipeline_phases.commands.build_phase_cmd` are used
where needed: ``build_phase_cmd`` physically lives under
``pipeline_phases/``, and deferring the import to call time keeps
the module graph acyclic. By the time ``route_with_ack`` /
``maybe_append_ack_calls`` / ``replay_snapshot`` actually run the
relevant modules are already loaded, so no cycle can form.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sdd_core import output
from review_quality.gate_session import get_phase_snapshot

from .actions import Action
from .envelope_keys import (
    KEY_NEXT_OPTIONS,
    NEXT_OPTIONS_KEY_COMMAND_TEMPLATE,
    NEXT_OPTIONS_KEY_RATIONALE,
    NEXT_OPTIONS_KEY_USER_CHOICE_ENUM,
    NEXT_OPTIONS_KEY_USER_CHOICE_EXCLUDED,
    NEXT_OPTIONS_KEY_USER_CHOICE_RECOMMENDED,
    PHASE_FLAG,
    PHASE_POST_REVIEW,
)
from .transitions import phase_key

if TYPE_CHECKING:  # pragma: no cover - import-time only
    from .phase_kit import PhaseContext
    from .snapshots import PhaseSnapshotBase

__all__ = (
    "NextOptions",
    "maybe_append_ack_calls",
    "route_with_ack",
    "replay_snapshot",
    "build_phase_chain",
    "build_phase_steps",
    "build_trivial_advance_chain",
)


@dataclass(frozen=True)
class NextOptions:
    """Conditional-next block emitted when ``next_action_command`` is null.

    Use ONLY when the substantive next step depends on caller intent
    (e.g. ``--phase post-fix`` after a NEEDS_WORK review). The agent
    reads :attr:`user_choice_recommended` to compose the literal.

    LSP invariant on every non-terminal envelope:
    ``(next_action_command non-null) XOR (next_options non-null)``.
    """

    command_template: str
    user_choice_enum: tuple[str, ...]
    user_choice_recommended: "str | None"
    user_choice_excluded: tuple[str, ...]
    rationale: str

    def to_payload(self) -> dict:
        """Return the JSON-serialisable dict form."""
        return {
            NEXT_OPTIONS_KEY_COMMAND_TEMPLATE: self.command_template,
            NEXT_OPTIONS_KEY_USER_CHOICE_ENUM: list(self.user_choice_enum),
            NEXT_OPTIONS_KEY_USER_CHOICE_RECOMMENDED: self.user_choice_recommended,
            NEXT_OPTIONS_KEY_USER_CHOICE_EXCLUDED: list(self.user_choice_excluded),
            NEXT_OPTIONS_KEY_RATIONALE: self.rationale,
        }


def build_phase_chain(commands: list[str]) -> str:
    """Return a ``&&``-joined Bash chain executable in one turn.

    Single source of truth for the "chain N pipeline-tick commands so
    the agent runs one Bash, the state machine advances N phases" shape.
    Used today by
    :func:`review.pipeline_phases.launch_preconditions.payload.build_recovery_chain`
    (per-reference reads + ack + relaunch) and
    :func:`review.pipeline_phases.post_fix._handle_post_fix`
    (clean-advance: ack-calls -> check-revalidation -> pre-approval).

    Empty / falsy entries are dropped so callers can pass optional
    elements without guarding each call site.
    """
    cleaned = _clean_commands(commands)
    if not cleaned:
        return ""
    return " && \\\n  ".join(cleaned)


def _clean_commands(commands: list[str]) -> list[str]:
    """Filter empty / non-string entries; preserve order."""
    return [c.strip() for c in commands if isinstance(c, str) and c.strip()]


def _step_name(command: str, idx: int) -> str:
    """Derive a stable step name from a shim command.

    Prefers the ``--phase X`` token (so chained pipeline-tick calls get
    distinct names); falls back to the script basename, then to a
    positional ``step-N``.
    """
    tokens = command.split()
    for i, token in enumerate(tokens):
        if token == PHASE_FLAG and i + 1 < len(tokens):
            return tokens[i + 1]
    for token in tokens:
        if token.endswith(".py"):
            base = token.rsplit("/", 1)[-1]
            return base[:-3] if base.endswith(".py") else base
    return f"step-{idx}"


def build_trivial_advance_chain(
    phase_cmds: dict, label: str,
) -> "tuple[str, str] | None":
    """Build the ack-calls → check-revalidation → pre-approval chain.

    Returns ``(chain, label)`` when every leg is populated and
    ``None`` when any required command is missing — the caller falls
    back to the legacy three-step flow. Single owner of the trivial-
    advance chain shape so post_review (zero-findings) and post_fix
    (proceed-without-modifications) attach byte-identical chains.

    The ``label`` is the telemetry / envelope label
    (``trivial_advance_to_pre_approval`` for post-review,
    ``post-fix-clean-advance`` for post-fix). The instruction string
    lives at :data:`review.pipeline_phases.constants.TRIVIAL_ADVANCE_INSTRUCTION`
    — callers stamp it on the result alongside the chain.
    """
    legs = [
        phase_cmds.get("ack_calls", "") if isinstance(phase_cmds, dict) else "",
        phase_cmds.get("check_revalidation", "") if isinstance(phase_cmds, dict) else "",
        phase_cmds.get("pre_approval", "") if isinstance(phase_cmds, dict) else "",
    ]
    if not all(isinstance(leg, str) and leg.strip() for leg in legs):
        return None
    chain = build_phase_chain(legs)
    if not chain:
        return None
    return chain, label


def build_phase_steps(commands: list[str]) -> list[dict]:
    """Return one ``{name, command}`` dict per cleaned command.

    Array view of :func:`build_phase_chain`. The two views are
    byte-isomorphic when joined back together::

        " && \\\\n  ".join(s["command"] for s in build_phase_steps(cs))
        == build_phase_chain(cs)

    Empty input → empty list (parallel to ``build_phase_chain([]) == ""``).
    """
    cleaned = _clean_commands(commands)
    return [
        {"name": _step_name(cmd, idx), "command": cmd}
        for idx, cmd in enumerate(cleaned, start=1)
    ]


def maybe_append_ack_calls(
    result: dict,
    ctx: "PhaseContext",
    *,
    lifecycle_flags: str = "",
) -> None:
    """Append an ``ack-calls`` follow-up when ``required_tool_calls`` is populated.

    Single source of truth for the "if pending → attach ack-calls command"
    pattern (was duplicated inline in ``launch.py`` and ``post_review.py``).
    Zero behaviour change: emits the same Shell call shape the callers
    built manually.
    """
    if not result.get("required_tool_calls"):
        return
    # Function-scope import: ``build_phase_cmd`` lives under
    # ``pipeline_phases/`` which imports us at module-scope via the
    # barrel re-exports. The cycle only forms at *module load* time —
    # deferring this import to call time sidesteps it entirely without
    # forcing a file move.
    from .pipeline_phases.commands import build_phase_cmd
    from .pipeline_phases.constants import PHASE_ACK_CALLS
    ack_cmd = build_phase_cmd(
        PHASE_ACK_CALLS,
        project_path=ctx.project_path,
        category=ctx.category,
        target_name=ctx.target_name,
        lifecycle_flags=lifecycle_flags,
    )
    # Emit a typed ``PipelineTick`` action so consumers dispatch on
    # ``kind`` + ``event`` while the ``Shell`` ``command`` shape stays
    # the literal contract for shell-side consumers. ``gate_id`` is
    # read off the session via
    # :func:`pipeline_tick._append_from_session`, so we ship an empty
    # string here to keep the typed payload stable across all emit
    # sites — the adapter resolves the authoritative value when it
    # actually runs the shell equivalent.
    result["required_tool_calls"].append(
        Action.pipeline_tick(
            event=PHASE_ACK_CALLS,
            command=ack_cmd,
            reason="Acknowledge pending tool calls to unblock next phase",
        )
    )


def route_with_ack(
    result: dict,
    ctx: "PhaseContext",
    *,
    forward_phase: str,
    forward_cmd: str = "",
    pending_instr: str,
    clear_instr: str,
    lifecycle_flags: str = "",
    extra_phase_commands: dict | None = None,
    next_options: "NextOptions | None" = None,
) -> None:
    """Set ``next_phase`` / ``next_action_command`` / ``instruction`` / ``phase_commands``.

    Invariant (see review-approval-pipeline.md § Pending Tool Calls):
    when a phase emits ``required_tool_calls``, ``next_action_command``
    MUST route through ack-calls before the forward phase runs.
    Complements :func:`maybe_append_ack_calls` — that helper owns
    appending the Shell call; this helper owns the routing shape.

    Parameters
    ----------
    forward_phase, forward_cmd:
        The substantive phase the pipeline should run after ack-calls
        clears. ``forward_phase`` is embedded in ``phase_commands`` under
        its hyphens-to-underscores alias (e.g. ``pre-approval`` →
        ``pre_approval``).
    pending_instr, clear_instr:
        Agent-facing instruction strings for the has-pending-calls and
        no-pending-calls branches respectively. Keeping the strings as
        parameters preserves per-handler vocabulary (e.g. "fix loop" vs
        "zero findings") without forking routing logic.
    extra_phase_commands:
        Extra ``phase_commands`` entries to merge on top of the
        ack/forward pair. Used by handlers that expose additional
        siblings (e.g. ``check_revalidation`` alongside ``pre_approval``).
    next_options:
        Pass when the substantive next step is conditional on caller
        intent. Mutually exclusive with ``forward_cmd``: passing both
        raises ``ValueError``. The block is JSON-serialised under
        ``result[KEY_NEXT_OPTIONS]`` and ``next_action_command`` is set
        to ``None`` so the LSP invariant
        ``(next_action_command non-null) XOR (next_options non-null)``
        holds at the routing layer.
    """
    if next_options is not None and forward_cmd:
        raise ValueError(
            "route_with_ack: pass either forward_cmd or next_options, not both"
        )
    # See :func:`maybe_append_ack_calls` — same function-scope import
    # rationale.
    from .pipeline_phases.commands import build_phase_cmd
    from .pipeline_phases.constants import PHASE_ACK_CALLS
    ack_cmd = build_phase_cmd(
        PHASE_ACK_CALLS,
        project_path=ctx.project_path,
        category=ctx.category,
        target_name=ctx.target_name,
        lifecycle_flags=lifecycle_flags,
    )
    if next_options is not None:
        result[KEY_NEXT_OPTIONS] = next_options.to_payload()
    has_pending = bool(result.get("required_tool_calls"))
    forward_key = phase_key(forward_phase)
    if has_pending:
        result["next_phase"] = PHASE_ACK_CALLS
        result["next_action_command"] = ack_cmd
        result["instruction"] = pending_instr
    else:
        result["next_phase"] = forward_phase
        # next_options carries the conditional verb selection — the
        # legitimate-null branch for next_action_command. Otherwise
        # emit the literal forward command.
        if next_options is not None:
            result["next_action_command"] = None
        else:
            result["next_action_command"] = forward_cmd
        result["instruction"] = clear_instr
    commands = {
        "ack_calls": ack_cmd,
        forward_key: forward_cmd,
    }
    if extra_phase_commands:
        commands.update(extra_phase_commands)
    result["phase_commands"] = commands


def replay_snapshot(
    session: dict, ctx: "PhaseContext", *,
    phase: str, expected_key: str, success_message: str,
    cls: "type[PhaseSnapshotBase]",
) -> bool:
    """Rebuild a cached phase response from its typed snapshot.

    Returns ``True`` iff the snapshot existed, its cache key matched
    ``expected_key``, and the response was emitted via
    :func:`output.success`. Shared by ``post_review`` and ``post_fix``
    so the replay shape stays identical (same helpers, same routing
    vocabulary, same emission).

    The typed snapshot is rebuilt via :meth:`cls.from_dict` and passed
    directly to :func:`route_with_ack`. ``required_tool_calls`` and
    ``todo_write_payload`` always ride on the agent-facing result dict
    — the per-phase snapshots store them verbatim.
    """
    snap = get_phase_snapshot(session, phase, cls=cls)
    if snap is None or getattr(snap, "key", None) != expected_key:
        return False
    raw = snap.to_dict()
    raw.pop("key", None)
    # ``other_phase`` / ``other_cmd`` survive on the persisted snapshot
    # for forward-compat replay of older sessions, but the replayed
    # envelope no longer surfaces an alternative-branch peer command:
    # the phase-graph is the canonical source of truth for downstream
    # phases (read via ``pipeline-tick.py --describe-phase-graph``).
    raw.pop("other_phase", None)
    raw.pop("other_cmd", None)
    result = dict(raw)
    result["idempotent_replay"] = True
    route_with_ack(
        result, ctx,
        forward_phase=getattr(snap, "forward_phase", "") or "",
        forward_cmd=getattr(snap, "forward_cmd", "") or "",
        pending_instr=getattr(snap, "pending_instr", "") or "",
        clear_instr=getattr(snap, "clear_instr", "") or "",
        lifecycle_flags=getattr(snap, "lifecycle_flags", "") or "",
    )
    # Replay the allowed/excluded ``--user-choice`` vocabularies from
    # the snapshot so fresh and idempotent post-review envelopes stay
    # byte-identical.
    if phase == PHASE_POST_REVIEW:
        from review_quality.constants import (
            SCOPE_PER_DOCUMENT as _SCOPE_PER_DOCUMENT,
            USER_CHOICE_ALLOWED as _UC,
        )
        from review.pipeline_phases.launch import (
            POST_FIX_USER_CHOICES_SOURCE_POST_REVIEW as _POST_REVIEW_SRC,
        )
        from review_quality.gate_session import (
            read_session as _read_session,
        )
        from sdd_core.command_templates import promote_post_fix_phase_command
        phase_cmds = result.get("phase_commands")
        if isinstance(phase_cmds, dict):
            allowed = getattr(snap, "post_fix_user_choices", None) or list(_UC)
            excluded = getattr(snap, "post_fix_user_choices_excluded", None) or []
            phase_cmds["post_fix_user_choices"] = list(allowed)
            phase_cmds["post_fix_user_choices_excluded"] = list(excluded)
            phase_cmds["post_fix_user_choices_source"] = _POST_REVIEW_SRC
            replay_session = _read_session(
                ctx.category, ctx.target_name, ctx.project_path,
            )
            replay_cached = replay_session.get("launch_args_cache") or {}
            replay_gate = replay_session.get("review_gate") or {}
            findings_count = int(getattr(snap, "actionable_findings", 0) or 0)
            scope = (
                replay_gate.get("review_scope")
                or replay_cached.get("scope", _SCOPE_PER_DOCUMENT)
            )
            promote_post_fix_phase_command(
                phase_cmds,
                category=ctx.category,
                target_name=ctx.target_name,
                project_path=replay_cached.get(
                    "project_path", ctx.project_path,
                ) or "",
                doc_list=replay_cached.get("doc_list", "") or "",
                fix_cycle=int(replay_gate.get("fix_cycle", 0) or 0),
                max_cycles=int(replay_gate.get("max_cycles", 0) or 0),
                scope=scope,
                findings_count=findings_count,
                parent_todo=ctx.parent_todo or "",
                gate_id=ctx.gate_id or "",
                lifecycle_flags=getattr(snap, "lifecycle_flags", "") or "",
            )
    output.success(result, success_message)
    return True
