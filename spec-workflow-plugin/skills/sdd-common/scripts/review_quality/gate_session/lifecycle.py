"""Session lifecycle: init, stale detection, gate advancement."""
from __future__ import annotations

import uuid
from typing import Optional

from sdd_core.time import ts_now
from ..constants import DEFAULT_MAX_FIX_CYCLES, STALE_INTERMEDIATE_STATES, GateState
from .io import (
    _default_review_gate,
    _default_session,
    read_session,
    session_path,
    write_session,
)
from sdd_core import output


def _new_gate_uuid() -> str:
    """Return a fresh ``g-<12-hex>`` gate UUID.

    Short prefix + 12-char uuid4 hex keeps the identifier compact
    enough to surface in log lines and trace metadata without
    sacrificing uniqueness (2^48 space is ample for per-workflow
    scopes). The prefix signals "gate" in mixed logs so operators
    don't confuse it with workflow IDs or PR identifiers.
    """
    return f"g-{uuid.uuid4().hex[:12]}"

__all__ = [
    "init_session",
    "detect_stale_entry",
    "record_user_accept",
    "get_user_accept_time",
    "advance_gate",
    "complete_gate",
    "record_executed_signature",
]


def record_executed_signature(gate: dict, signature: str) -> None:
    """Append *signature* to ``executed_tool_calls_signatures`` if absent.

    Mutates *gate* in place. Single owner for the dedup-on-append rule
    so callers (ack-calls, future replay paths) cannot drift on the
    insertion semantics.
    """
    if not signature:
        return
    from .keys import GATE_EXECUTED_TOOL_CALLS_SIGNATURES
    history = gate.get(GATE_EXECUTED_TOOL_CALLS_SIGNATURES) or []
    if signature not in history:
        history.append(signature)
    gate[GATE_EXECUTED_TOOL_CALLS_SIGNATURES] = history


def _preserve_fix_loop_state(prior_gate: dict, new_gate: dict) -> None:
    """Carry forward active_todos and fix_cycle from a prior gate so that
    _handle_zero_findings can finalize cycle TODOs after a re-launch."""
    prior_cycle = prior_gate.get("fix_cycle", 0)
    if prior_cycle > 0 and prior_gate.get("active_todos"):
        new_gate["active_todos"] = prior_gate["active_todos"]
        new_gate["fix_cycle"] = prior_cycle


def init_session(
    *, category: str, target_name: str, workflow_mode: str,
    gate_id: str, parent_todo_id: str, max_cycles: int = DEFAULT_MAX_FIX_CYCLES,
    project_path: str = ".", parent_todo_content: str | None = None,
) -> dict:
    """Create or reset a session file based on workflow_mode.

    - create:  Always start fresh (structural fix for stale state issue).
    - update:  Preserve if gate matches, reset if different gate.
    - resume:  Preserve existing state; auto-reset stale intermediate states.
    """
    path = session_path(category, target_name, project_path)
    existing = output.safe_read_json(path, default=None)
    now = ts_now()

    if workflow_mode == "create" or not existing or not isinstance(existing, dict):
        session = _default_session()
        session["category"] = category
        session["target_name"] = target_name
        session["workflow_mode"] = workflow_mode
        session["started_at"] = now
        session["updated_at"] = now
        session["review_gate"] = _default_review_gate(
            gate_id=gate_id, parent_todo_id=parent_todo_id,
            parent_todo_content=parent_todo_content,
            max_cycles=max_cycles,
            gate_uuid=_new_gate_uuid(),
        )
        write_session(category, target_name, session, project_path)
        return session

    full = read_session(category, target_name, project_path)
    gate = full.get("review_gate") or {}

    if workflow_mode == "update":
        if gate.get("gate_id") and gate["gate_id"] != gate_id:
            prior_gate = dict(gate)
            full["review_gate"] = _default_review_gate(
                gate_id=gate_id, parent_todo_id=parent_todo_id,
                parent_todo_content=parent_todo_content,
                max_cycles=max_cycles,
                gate_uuid=_new_gate_uuid(),
            )
            _preserve_fix_loop_state(prior_gate, full["review_gate"])
        else:
            gate["gate_id"] = gate_id
            gate["parent_todo_id"] = parent_todo_id
            gate["max_cycles"] = max_cycles
            # Backfill ``gate_uuid`` on sessions persisted before the
            # field existed so later ``pipeline/tick`` dispatch has a
            # stable handle even when the same gate resumes.
            if not gate.get("gate_uuid"):
                gate["gate_uuid"] = _new_gate_uuid()
            # Resume path: only adopt caller-supplied content when
            # provided; an omitted kwarg preserves the prior content.
            if parent_todo_content is not None:
                gate["parent_todo_content"] = parent_todo_content
        full["workflow_mode"] = workflow_mode
        full["updated_at"] = now
        write_session(category, target_name, full, project_path)
        return full

    stale = detect_stale_entry(full)
    if stale["is_stale"]:
        full["review_gate"] = _default_review_gate(
            gate_id=gate_id, parent_todo_id=parent_todo_id,
            parent_todo_content=parent_todo_content,
            max_cycles=max_cycles,
            gate_uuid=_new_gate_uuid(),
        )
    else:
        gate["gate_id"] = gate_id
        gate["parent_todo_id"] = parent_todo_id
        gate["max_cycles"] = max_cycles
        if not gate.get("gate_uuid"):
            gate["gate_uuid"] = _new_gate_uuid()
        if parent_todo_content is not None:
            gate["parent_todo_content"] = parent_todo_content
    full["workflow_mode"] = workflow_mode
    full["updated_at"] = now
    write_session(category, target_name, full, project_path)
    return full


def detect_stale_entry(session_data: dict) -> dict:
    """Detect review_gate left over from a previous interrupted session.

    Intermediate (non-persistable) states: FIX, RE_VALIDATE, PRESENT, RE_REVIEW.
    Terminal/safe: None, MAX_CYCLES_EXHAUSTED, DONE.
    """
    gate = session_data.get("review_gate") or {}
    state = gate.get("current_state")

    if state in STALE_INTERMEDIATE_STATES:
        # REVIEW_COMPLETE with active TODOs = mid-fix-loop, not stale
        if state == GateState.REVIEW_COMPLETE and gate.get("active_todos"):
            return {
                "is_stale": False,
                "reason": "REVIEW_COMPLETE with active fix-loop TODOs (mid-session)",
                "recommendation": None,
            }
        return {
            "is_stale": True,
            "reason": f"Gate stuck in intermediate state '{state}'",
            "recommendation": "Reset with --workflow-mode create or resume (auto-resets)",
        }

    return {
        "is_stale": False,
        "reason": "Gate state is safe or empty",
        "recommendation": None,
    }


def record_user_accept(session_data: dict) -> dict:
    """Record that the user explicitly accepted current changes."""
    gate = session_data.get("review_gate") or {}
    gate["user_accepted_at"] = ts_now()
    return session_data


def get_user_accept_time(session_data: dict) -> Optional[str]:
    """Return the user_accepted_at timestamp, or None."""
    gate = session_data.get("review_gate") or {}
    return gate.get("user_accepted_at")


def advance_gate(
    session_data: dict, *, reset_cursor: bool = False, **updates,
) -> dict:
    """Update review_gate fields, auto-set updated_at. Returns session.

    Single writer for ``last_completed_phase`` /
    ``last_completed_user_choice`` so cursor reset and cursor advance
    flow through one seam. Pass ``reset_cursor=True`` from replay paths
    to clear both fields atomically.
    """
    gate = session_data.get("review_gate")
    if gate is None:
        gate = _default_review_gate()
        session_data["review_gate"] = gate
    if reset_cursor:
        gate.pop("last_completed_phase", None)
        gate.pop("last_completed_user_choice", None)
    for key, value in updates.items():
        gate[key] = value
    session_data["updated_at"] = ts_now()
    return session_data


def complete_gate(session_data: dict, gate_id: str) -> dict:
    """Mark gate as completed in completed_gates, clear review_gate."""
    completed = session_data.get("completed_gates") or []
    if gate_id not in completed:
        completed.append(gate_id)
    session_data["completed_gates"] = completed
    session_data["review_gate"] = _default_review_gate()
    session_data["updated_at"] = ts_now()
    return session_data
