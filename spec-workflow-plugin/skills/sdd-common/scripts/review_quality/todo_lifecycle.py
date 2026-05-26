"""TODO lifecycle state transitions for the review-gate fix-loop pipeline.

Generates exact TodoWrite payloads for pipeline events. Returned
``todo_write_payload`` is passed straight to TodoWrite with zero
reshaping. Errors are reported structurally — no exceptions raised;
invalid inputs yield empty lists or ``{"error": ...}`` envelopes.
"""
from __future__ import annotations

import re

from .constants import (
    DEFAULT_MAX_FIX_CYCLES,
    GateState,
    SCOPE_PER_DOCUMENT,
    TODO_CONTENT_TEMPLATES,
    TODO_ID_PREFIXES,
    TODO_PHASES,
    TodoStatus,
)

_VALID_REVIEW_SCOPES = frozenset({
    "per-document", "final", "steering", "spec", "discovery",
})


def has_completed_work(active_todos: list[dict]) -> bool:
    """Return True if any active TODO has been completed (work was done)."""
    return any(
        t.get("status") == TodoStatus.COMPLETED for t in active_todos
    )


def finalize_active_todos(
    active_todos: list[dict],
    terminal_status: str = TodoStatus.CANCELLED,
) -> list[dict]:
    """Finalize all in_progress/pending cycle TODOs with the given status."""
    return [
        {"id": at["id"], "content": at.get("content", at["id"]),
         "status": terminal_status}
        for at in active_todos
        if at.get("status") in (TodoStatus.IN_PROGRESS, TodoStatus.PENDING)
    ]


def _todo_id(namespace: str, number: int, phase: str) -> str:
    return f"{TODO_ID_PREFIXES[namespace]}{number}-{phase}"


def cycle_todo_id(cycle: int, phase: str) -> str:
    """Build a canonical todo ID for a fix-loop cycle phase."""
    return _todo_id("fix_cycle", cycle, phase)


def reentry_todo_id(reentry_count: int, phase: str) -> str:
    """Build a canonical todo ID for a stale-doc re-entry phase.

    Stale-doc re-entry is bookkept separately from the bounded fix-loop
    cycle so agents and users can distinguish "still inside the
    max_fix_cycles budget" from "max cycles reached; pre-approval
    surfaced stale docs and forced a fresh review".
    """
    return _todo_id("reentry", reentry_count, phase)


# Agent-flavoured aliases for the lifecycle phases the pipeline owns.
# Real agents pre-author TODOs with these naturalistic IDs (``approve``,
# ``review-gate``, etc.) rather than the canonical phase-module names.
# Keeping the set explicit beats a looser ``approve.*`` regex: the
# former fails closed on a new synonym (test adds one row, done); the
# latter would silently subsume unrelated IDs like ``approve-budget``.
_PHASE_SYNONYMS: frozenset[str] = frozenset({
    "approve", "approval", "pre-approval",
    "approval-formal", "approval-formal-required",
    "review", "review-gate", "post-review", "post-fix",
    "pre-launch-check", "complete",
})


def _registered_phase_cli_names() -> frozenset[str]:
    """Return the CLI sub-command names the registry registers.

    Reads the phase registry directly. Package import of
    :mod:`review.pipeline_phases` fires every ``@phase`` decorator, so
    :func:`registered_phases` is the single source of truth for
    "what's a phase".

    Late imports avoid a circular edge: ``launch`` imports this module,
    so a top-level import of the registry at module load would deadlock.
    """
    import review.pipeline_phases  # noqa: F401 — populates the registry
    from review.phase_kit import registered_phases

    return frozenset(registered_phases().keys())


def _phase_token_patterns() -> tuple[str, ...]:
    """Derive displacement patterns from the CLI phase names + synonyms.

    Resolving at call time keeps the registry as the single source of
    truth — adding a new phase auto-joins the displacement set without
    touching this module.
    """
    tokens = set(_registered_phase_cli_names())
    tokens |= _PHASE_SYNONYMS
    return tuple(rf"^{re.escape(t)}(-.+)?$" for t in sorted(tokens))


def displaces_todo_id_hints() -> list[str]:
    """Return the regex hints whose IDs the pipeline subsumes.

    Derived from two data sources — the pipeline phase registry and the
    agent-flavoured synonym set — plus the ``stepN`` scaffold regex.
    Consumers (``launch``, ``post_fix``) MUST go through this function
    rather than re-declare the vocabulary inline.
    """
    return [r"^step\d+$", *_phase_token_patterns()]


def matches_displaceable_todo(todo_id: str) -> bool:
    """Return ``True`` when ``todo_id`` is subsumed by a pipeline hint.

    Call-site convenience: consumers prefer this predicate over
    re-compiling :func:`displaces_todo_id_hints` themselves, which
    would duplicate the regex vocabulary outside this module.
    """
    if not todo_id:
        return False
    for pattern in displaces_todo_id_hints():
        if re.match(pattern, todo_id):
            return True
    return False


def build_owned_todo_ids_note() -> str:
    """Return the canonical agent-facing note for ``owned_todo_ids``.

    The prose is derived from the same data surface as
    :func:`displaces_todo_id_hints` so a new synonym cannot contradict
    the human-readable message.
    """
    return (
        "The pipeline owns these TODO IDs for this gate. Do not "
        "pre-author `stepN`, `approve*`, or `review*`-family trackers — "
        "the displaces_todo_id_hints patterns mark such IDs as "
        "subsumed by owned_todo_ids."
    )


def build_owned_todo_ids(
    parent_todo: str, fix_cycle: int, reentry_count: int = 0,
) -> list[str]:
    """Return every TODO ID the pipeline emits for ``parent_todo``.

    The pipeline owns its full tracker list so SKILL.md prose never
    has to tell the agent to pre-author a matching ``stepN`` scaffold.

    The list always includes ``parent_todo`` itself. For ``fix_cycle >
    0`` it also includes the current cycle's apply / validate / review
    IDs. For ``reentry_count > 0`` it additionally includes the
    current stale-doc re-entry triad (``reentry-rM-*``).
    """
    owned = [parent_todo]
    if fix_cycle > 0:
        owned.extend(
            cycle_todo_id(fix_cycle, phase) for phase in TODO_PHASES
        )
    if reentry_count > 0:
        owned.extend(
            reentry_todo_id(reentry_count, phase) for phase in TODO_PHASES
        )
    return owned


def _error(msg: str) -> dict:
    return {"error": msg, "todo_write_payload": None}


def _build_three_phase_todos(
    namespace: str, number: int, review_scope: str,
) -> list[dict]:
    """Shared three-phase (apply / validate / review) TODO builder.

    Fix-loop cycle TODOs and stale-doc re-entry TODOs differ only in
    ID namespace + content wording; both read the same declarative
    table from ``constants``. Returns ``[]`` for invalid
    ``review_scope`` so callers see a structural error signal rather
    than an exception.
    """
    if review_scope not in _VALID_REVIEW_SCOPES:
        return []
    tmpl = TODO_CONTENT_TEMPLATES[namespace]
    statuses = (
        TodoStatus.IN_PROGRESS, TodoStatus.PENDING, TodoStatus.PENDING,
    )
    return [
        {
            "id": _todo_id(namespace, number, phase),
            "content": tmpl[phase].format(n=number, review_scope=review_scope),
            "status": status,
        }
        for phase, status in zip(TODO_PHASES, statuses)
    ]


def build_cycle_todos(
    cycle: int, review_scope: str = SCOPE_PER_DOCUMENT,
) -> list[dict]:
    """Generate the three cycle-level TODOs for a fix cycle.

    Returns an empty list (rather than raising) for invalid
    ``review_scope`` so callers get a structural error signal.
    """
    return _build_three_phase_todos("fix_cycle", cycle, review_scope)


def build_reentry_todos(
    reentry_count: int, review_scope: str = SCOPE_PER_DOCUMENT,
) -> list[dict]:
    """Generate the three phase TODOs for a stale-doc re-entry.

    Mirrors :func:`build_cycle_todos` but uses the ``reentry-rM-*``
    namespace + distinct content wording so the TODO panel surfaces a
    forced re-review on stale docs as a separate concern from an
    in-budget fix cycle. Returns ``[]`` for invalid ``review_scope``.
    """
    return _build_three_phase_todos("reentry", reentry_count, review_scope)


def _payload(todos: list[dict], explanation: str) -> dict:
    return {
        "todo_write_payload": {"todos": todos, "merge": True},
        "explanation": explanation,
    }


def _handle_enter_fix_loop(ctx: dict) -> dict:
    if ctx["current_state"] == GateState.FIX:
        return _error(
            "Cannot enter_fix_loop: current_state is already FIX "
            "(expected null or PRESENT). Possible duplicate phase call."
        )
    # Cycle TODOs are deferred to post-fix (sole emitter) to avoid
    # double-delivery when both post-review and post-fix emit them.
    return _payload(
        [{"id": ctx["parent_todo_id"], "content": ctx["parent_content"],
          "status": TodoStatus.IN_PROGRESS}],
        "Fix loop entered. Cycle TODOs deferred to post-fix phase.",
    )


def _handle_zero_findings(ctx: dict) -> dict:
    todos = [{"id": ctx["parent_todo_id"], "content": ctx["parent_content"],
              "status": TodoStatus.COMPLETED}]
    active = ctx.get("active_todos", [])
    if has_completed_work(active):
        todos.extend(finalize_active_todos(active, TodoStatus.COMPLETED))
        explanation = "Review passed with zero findings. Cycle TODOs completed (fixes verified)."
    else:
        todos.extend(finalize_active_todos(active))
        explanation = "Review passed with zero findings. Cycle TODOs cancelled."
    return _payload(todos, explanation)


def _handle_cycle_advance(ctx: dict) -> dict:
    active_todos = ctx["active_todos"]
    if not active_todos:
        return _error(
            "Cannot cycle_advance: no active_todos in review_gate."
        )
    fix_cycle = ctx["fix_cycle"]
    review_scope = ctx["review_scope"]
    todos = [{"id": ctx["parent_todo_id"], "content": ctx["parent_content"],
               "status": TodoStatus.IN_PROGRESS}]
    apply_id = cycle_todo_id(fix_cycle, "apply")
    validate_id = cycle_todo_id(fix_cycle, "validate")
    review_id = cycle_todo_id(fix_cycle, "review")
    tmpl = TODO_CONTENT_TEMPLATES["fix_cycle"]

    active_map = {t["id"]: t.get("status") for t in active_todos}

    if active_map.get(apply_id) == TodoStatus.IN_PROGRESS:
        todos.extend([
            {"id": apply_id,
             "content": tmpl["apply"].format(n=fix_cycle),
             "status": TodoStatus.COMPLETED},
            {"id": validate_id,
             "content": tmpl["validate"].format(n=fix_cycle),
             "status": TodoStatus.IN_PROGRESS},
            {"id": review_id,
             "content": tmpl["review"].format(n=fix_cycle, review_scope=review_scope),
             "status": TodoStatus.PENDING},
        ])
        return _payload(
            todos,
            f"Cycle {fix_cycle}: apply→completed, "
            f"validate→in_progress.",
        )
    elif active_map.get(validate_id) == TodoStatus.IN_PROGRESS:
        todos.extend([
            {"id": validate_id,
             "content": tmpl["validate"].format(n=fix_cycle),
             "status": TodoStatus.COMPLETED},
            {"id": review_id,
             "content": tmpl["review"].format(n=fix_cycle, review_scope=review_scope),
             "status": TodoStatus.IN_PROGRESS},
        ])
        return _payload(
            todos,
            f"Cycle {fix_cycle}: validate→completed, "
            f"review→in_progress.",
        )
    else:
        next_cycle = fix_cycle + 1
        target_prefix = f"{TODO_ID_PREFIXES['fix_cycle']}{next_cycle}-"
        if any(t.get("id", "").startswith(target_prefix) for t in active_todos):
            return _payload(
                [{"id": ctx["parent_todo_id"], "content": ctx["parent_content"],
                  "status": TodoStatus.IN_PROGRESS},
                 *active_todos],
                f"Cycle {fix_cycle}: active_todos already at cycle {next_cycle} "
                f"(idempotent). Returning as-is.",
            )
        return _error(
            f"Cannot cycle_advance: no in_progress TODO found in "
            f"active_todos for cycle {fix_cycle}. "
            f"Active: {active_map}"
        )


def _handle_fix_loop_exit(ctx: dict) -> dict:
    terminal = ctx["rg"].get("terminal_state")
    parent_status = TodoStatus.COMPLETED if terminal == GateState.PASS else TodoStatus.IN_PROGRESS
    cycle_status = TodoStatus.COMPLETED if terminal == GateState.PASS else TodoStatus.CANCELLED
    todos = [{"id": ctx["parent_todo_id"], "content": ctx["parent_content"],
               "status": parent_status}]
    todos.extend(finalize_active_todos(ctx["active_todos"], cycle_status))
    return _payload(
        todos,
        f"Fix loop exited with terminal_state={terminal}. "
        f"Remaining cycle TODOs finalized.",
    )


def _handle_re_entry(ctx: dict) -> dict:
    """Emit stale-doc re-entry TODOs in the ``reentry-rM-*`` namespace.

    This is not the fix loop — ``max_fix_cycles`` bounds the fix loop
    literally. Stale-doc re-entry is a forced re-review triggered by
    ``pre_approval`` when docs were modified after their last review,
    and uses its own ``reentry_count`` counter so the two concerns
    never collide in the TODO panel.

    ``reentry_count`` is the single authority — ``pre_approval``
    increments it atomically before routing back to ``launch``, and
    this handler emits ``reentry-r{reentry_count}-*`` IDs using the
    current value (no internal bump). Replaying this event with the
    same count emits the same TODO IDs.
    """
    reentry_count = max(int(ctx.get("reentry_count") or 0), 1)
    todos = [
        {"id": ctx["parent_todo_id"], "content": ctx["parent_content"],
         "status": TodoStatus.IN_PROGRESS},
        *build_reentry_todos(reentry_count, ctx["review_scope"]),
    ]
    return _payload(
        todos,
        f"Stale-doc re-entry (attempt {reentry_count}). "
        f"Fix-loop budget ({ctx['max_cycles']}) is preserved; "
        f"this is a forced re-review on stale docs. "
        f"Parent {ctx['parent_todo_id']} stays in_progress.",
    )


_EVENT_HANDLERS = {
    "enter_fix_loop": _handle_enter_fix_loop,
    "zero_findings": _handle_zero_findings,
    "cycle_advance": _handle_cycle_advance,
    "fix_loop_exit": _handle_fix_loop_exit,
    "re_entry": _handle_re_entry,
}


# Canonical ID for the agent-facing approval tracker. ``matches_displaceable_todo``
# subsumes every variant (``approve``, ``approval``, ``pre-approval``,
# ``approval-formal``, ``approval-formal-required``, ...) so emitting the
# canonical form keeps the displacement contract self-consistent —
# whatever the agent pre-authored falls under the pipeline's vocabulary.
_APPROVAL_TRACKER_ID = "approve"
_APPROVAL_TRACKER_CONTENT = "Pre-approval review and approval"


def next_in_progress_todo(
    event: str, parent_todo_id: str, session_data: dict,
) -> dict | None:
    """Return the next agent-owned tracker to move to ``in_progress``.

    Events that mark the review-gate parent as ``completed`` leave no
    TODO in-progress, which triggers the IDE warning "No TODOs are
    marked in-progress". The pipeline emits the next expected tracker
    (the approval step) as part of the same ``todo_write_payload`` so
    the agent applies one TodoWrite call.

    Events where the parent remains ``in_progress`` (``enter_fix_loop``,
    ``cycle_advance``, ``re_entry``) already have an active tracker and
    return ``None``.

    :param event: The lifecycle event emitting the payload.
    :param parent_todo_id: Currently unused but kept in the signature
        for forward-compatibility — a future event might key the
        transition ID off the parent.
    :param session_data: Full gate-session dict. Consulted for
        ``terminal_state`` on ``fix_loop_exit``.
    """
    if event == "zero_findings":
        return {
            "id": _APPROVAL_TRACKER_ID,
            "content": _APPROVAL_TRACKER_CONTENT,
            "status": TodoStatus.IN_PROGRESS,
        }
    if event == "fix_loop_exit":
        rg = session_data.get("review_gate") or {}
        if rg.get("terminal_state") == GateState.PASS:
            return {
                "id": _APPROVAL_TRACKER_ID,
                "content": _APPROVAL_TRACKER_CONTENT,
                "status": TodoStatus.IN_PROGRESS,
            }
    return None


def compute_todo_payload(
    event: str,
    parent_todo_id: str,
    session_data: dict,
    review_scope: str = SCOPE_PER_DOCUMENT,
) -> dict:
    """Return the exact TodoWrite payload for a pipeline event.

    Reads fix_cycle, max_cycles, current_state, and active_todos from
    session_data["review_gate"] internally.

    Returns:
        On success: {"todo_write_payload": {"todos": [...], "merge": true},
                     "explanation": "..."}
        On error:   {"error": "...", "todo_write_payload": null}
    """
    handler = _EVENT_HANDLERS.get(event)
    if not handler:
        return _error(
            f"Invalid event '{event}'. Valid: {sorted(_EVENT_HANDLERS)}"
        )

    if not parent_todo_id:
        return _error("parent_todo_id is required")

    rg = session_data.get("review_gate")
    if not rg or not isinstance(rg, dict):
        if event == "zero_findings":
            return _payload(
                [{"id": parent_todo_id,
                  "content": f"Review gate: {parent_todo_id}",
                  "status": TodoStatus.COMPLETED}],
                "Review passed with zero findings. No review_gate needed.",
            )
        return _error(
            f"Missing review_gate in session_data for event '{event}'."
        )

    ctx = {
        "rg": rg,
        "fix_cycle": rg.get("fix_cycle", 0),
        "max_cycles": rg.get("max_cycles", DEFAULT_MAX_FIX_CYCLES),
        "reentry_count": rg.get("reentry_count", 0),
        "current_state": rg.get("current_state"),
        "active_todos": rg.get("active_todos", []),
        "parent_todo_id": parent_todo_id,
        # Fallback keeps the payload shape stable for sessions predating
        # ``parent_todo_content``.
        "parent_content": rg.get("parent_todo_content") or f"Review gate: {parent_todo_id}",
        "review_scope": review_scope,
    }

    result = handler(ctx)
    if result.get("error"):
        return result
    transition = next_in_progress_todo(event, parent_todo_id, session_data)
    if transition is not None:
        payload = result.get("todo_write_payload") or {}
        todos = list(payload.get("todos") or [])
        if not any(
            (t.get("id") == transition["id"]
             and t.get("status") == TodoStatus.IN_PROGRESS)
            for t in todos
        ):
            todos.append(transition)
            payload["todos"] = todos
            result["todo_write_payload"] = payload
    return result
