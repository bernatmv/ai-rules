"""Phase entry guards and tool-call persistence for the review pipeline."""
from __future__ import annotations

import argparse
import hashlib
import json
from typing import Optional

from review_quality.gate_session import (
    GATE_EXECUTED_TOOL_CALLS_SIGNATURES,
    GATE_PENDING_CALLS,
    GATE_PENDING_CALLS_ACKED_SIGNATURE,
    GATE_PENDING_CALLS_SIGNATURE,
)

from ..actions import Action
from ..transitions import allowed_previous
from .commands import build_phase_cmd


def _canonicalise_call(call: dict) -> dict:
    """Return a stable, payload-only view of a single required tool call.

    Excludes mutable / advisory fields that drift across emissions
    (``reason`` text rewording, ``severity`` rollups). The kept fields
    are the ones an agent must execute — ``kind`` / ``tool`` / ``args``
    — so two emissions of the *same* TodoWrite payload hash identically.
    """
    if not isinstance(call, dict):
        return {}
    keep = ("kind", "tool", "args", "event")
    out: dict = {}
    for key in keep:
        if key in call:
            out[key] = call[key]
    return out


def hash_tool_calls(calls: list) -> str:
    """SHA-256 over the canonicalised representation of *calls*.

    Stable across the gate-session's lifetime: the same set of pending
    calls always hashes to the same value, so a previously-acked
    payload can be detected even after a session round-trip. Used by
    :func:`persist_pending_calls` to detect a previously-acked payload.
    """
    canonical = [_canonicalise_call(c) for c in (calls or [])]
    blob = json.dumps(canonical, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# Single source of truth for the no-op instruction emitted on a
# previously-acked re-emission. Phase handlers read this constant so
# the wording cannot drift between launch / post-review / pre-approval.
ALREADY_ACKED_INSTRUCTION = (
    "calls already acknowledged this gate; proceed"
)


def check_phase_sequence(session: dict, current_phase: str) -> Optional[dict]:
    """Return a blocked payload if the current phase isn't the expected next phase.

    Soft validation: passes silently when required_next_phase is None
    (fresh session, pre-existing gate dict, or first phase call).

    The allowed-previous set is derived from
    :data:`review.transitions.TRANSITIONS` rather than carried in a
    side-channel alias map. Adding a new edge to the graph
    automatically widens the acceptance window here.
    """
    gate = session.get("review_gate") or {}
    expected = gate.get("required_next_phase")
    if expected is None:
        return None

    allowed = allowed_previous(expected)
    if current_phase in allowed:
        return None

    cached = session.get("launch_args_cache", {})
    redirect_cmd = build_phase_cmd(
        expected,
        project_path=cached.get("project_path", "."),
        category=session.get("category", ""),
        target_name=session.get("target_name", ""),
        lifecycle_flags=cached.get("lifecycle_flags", ""),
    )

    # Embed the recovery literal in both ``reason`` and ``instruction``
    # so log-only viewers see the exact command without expanding the
    # next_action_command field. The agent still reads
    # ``next_action_command`` for routing — the literal in the message
    # body is the human-readable copy that lands in transcripts.
    return {
        "status": "blocked",
        "reason": (
            f"Phase sequence violation: expected '{expected}', got "
            f"'{current_phase}'. Recovery: run `{redirect_cmd}` to advance "
            f"the gate to '{expected}', then retry."
        ),
        "expected_phase": expected,
        "actual_phase": current_phase,
        "next_action_command": redirect_cmd,
        "instruction": (
            f"Run `{redirect_cmd}` (auto-resolves to '{expected}'), then "
            f"retry the original phase call."
        ),
    }


def phase_entry_guard(
    category: str, target_name: str, project_path: str, current_phase: str,
) -> tuple[dict, Optional[dict]]:
    """Read session and run both entry guards. Returns (session, blocked_or_None)."""
    from review_quality.gate_session import read_session

    session = read_session(category, target_name, project_path)

    pending = check_pending_calls(session)
    if pending:
        return session, pending

    sequence = check_phase_sequence(session, current_phase)
    if sequence:
        return session, sequence

    return session, None


def check_pending_calls(session: dict) -> Optional[dict]:
    """Return a 'blocked' payload if gate has unresolved pending_tool_calls.

    Returns None if no pending calls (safe to proceed).
    """
    gate = session.get("review_gate") or {}
    pending = gate.get(GATE_PENDING_CALLS) or []
    if not pending:
        return None
    return {
        "status": "blocked",
        "reason": "Pending tool calls from previous phase not yet acknowledged",
        "required_tool_calls": pending,
        "next_action": (
            "Execute the required_tool_calls above, then run "
            "pipeline-tick (auto-resolves to ack-calls)"
        ),
    }


def attach_todo_calls(result: dict, todo_result: Optional[dict]) -> None:
    """Wrap todo_write_payload into required_tool_calls for agent execution.

    Emits a typed ``TodoWrite`` action via :meth:`Action.todo_write`
    so consumers can dispatch on ``kind`` while still reading
    ``tool`` / ``args`` unchanged for compatibility with older
    envelopes.
    """
    if not todo_result:
        return
    payload = todo_result.get("todo_write_payload")
    if todo_result.get("error"):
        result["todo_write_error"] = todo_result["error"]
    if payload:
        result["todo_write_payload"] = payload
        result.setdefault("required_tool_calls", []).append(
            Action.todo_write(
                payload, reason="Sync pipeline TODO state to IDE",
            )
        )


def _signature_already_acked(gate: dict, signature: str) -> bool:
    """True when *signature* matches a previously-executed payload signature.

    Considers both the most recent acked signature and the historical
    ``executed_tool_calls_signatures`` ledger so dedupe survives
    non-adjacent re-emissions across the gate's lifetime.
    """
    if not signature:
        return False
    acked = gate.get(GATE_PENDING_CALLS_ACKED_SIGNATURE) or ""
    if signature == acked:
        return True
    history = gate.get(GATE_EXECUTED_TOOL_CALLS_SIGNATURES) or []
    return signature in history


def _emit_already_acked_marker(result: dict, signature: str = "") -> None:
    """Clear required_tool_calls and stamp the no-op instruction.

    The result dict is mutated in place. The gate is left untouched so
    a future *different* payload still hashes against the acked
    signature. ``signature`` is surfaced under ``executed_already`` so
    operators can audit which payload was suppressed.
    """
    result["required_tool_calls"] = []
    if signature:
        result["executed_already"] = [signature]
    existing = result.get("instruction") or ""
    if ALREADY_ACKED_INSTRUCTION not in existing:
        result["instruction"] = (
            f"{existing}\n{ALREADY_ACKED_INSTRUCTION}".strip()
        )


def persist_pending_calls(gate: dict, result: dict) -> None:
    """Record required_tool_calls into gate['pending_tool_calls'] before session write.

    Entries are copied verbatim so the typed-action metadata
    (``kind``, ``severity``, ``event``) survives the round-trip
    through ``check_pending_calls``. A shallow ``dict(c)``
    per entry keeps the mutation boundary at the gate edge without
    leaking future field additions from this helper.

    Idempotency — when the freshly-computed signature matches the
    last-acked signature on the gate, the agent has already executed
    this exact payload. The orchestrator delegates the suppress branch
    to :func:`_emit_already_acked_marker` so the persist branch and
    the suppress branch each own one decision.
    """
    calls = result.get("required_tool_calls") or []
    if not calls:
        gate.setdefault(GATE_PENDING_CALLS, [])
        return
    signature = hash_tool_calls(calls)
    if _signature_already_acked(gate, signature):
        _emit_already_acked_marker(result, signature=signature)
        gate.setdefault(GATE_PENDING_CALLS, [])
        return
    gate[GATE_PENDING_CALLS] = [dict(c) for c in calls]
    gate[GATE_PENDING_CALLS_SIGNATURE] = signature


def ack_reference_reads_uses_batched(args: argparse.Namespace) -> bool:
    """Return True when the ``ack-reference-reads`` phase was given ``--references``.

    Callers use this to skip the singular ``--reference-name`` /
    ``--echoed-sha256`` missing-flag check.
    """
    return (
        getattr(args, "phase", None) == "ack-reference-reads"
        and bool(getattr(args, "references", None))
    )
