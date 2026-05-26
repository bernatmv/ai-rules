"""Envelope-construction helpers for phase handlers."""
from __future__ import annotations

from typing import Iterable

from review_quality.gate_session import (
    GATE_EXECUTED_TOOL_CALLS_SIGNATURES,
    GATE_MAX_CYCLES,
    GATE_PENDING_CALLS_ACKED_SIGNATURE,
    GATE_REENTRY_COUNT,
    GATE_REENTRY_CYCLE,
    GATE_REENTRY_INSTRUCTION,
)
from review_quality.constants import DEFAULT_MAX_FIX_CYCLES
from sdd_core.text import ordinal

from ..transitions import TRANSITIONS, phase_key

__all__ = [
    "valid_phase_command_keys",
    "filter_phase_commands",
    "suppress_repeated_tool_calls",
    "stamp_reentry_metadata",
]


def valid_phase_command_keys(
    current_phase: str, *, has_pending_calls: bool = False,
) -> frozenset[str]:
    """Return the snake_case set of phase_commands keys reachable from
    ``current_phase`` via :data:`TRANSITIONS`.

    Adds ``ack_calls`` when ``has_pending_calls`` is True.
    """
    nexts = TRANSITIONS.get(current_phase, frozenset())
    keys = {phase_key(p) for p in nexts}
    if has_pending_calls:
        keys.add("ack_calls")
    return frozenset(keys)


def filter_phase_commands(
    commands: dict[str, str],
    current_phase: str,
    *,
    has_pending_calls: bool = False,
    extra_keys: Iterable[str] = (),
) -> dict[str, str]:
    """Filter ``commands`` so only keys reachable from ``current_phase``
    via :data:`TRANSITIONS` (plus optional ack-calls and ``extra_keys``)
    remain. The relative ordering of input items is preserved.
    """
    valid = set(valid_phase_command_keys(
        current_phase, has_pending_calls=has_pending_calls,
    ))
    valid.update(extra_keys)
    return {k: v for k, v in commands.items() if k in valid}


def suppress_repeated_tool_calls(
    payload: list[dict],
    gate: dict,
) -> tuple[list[dict], list[str]]:
    """Drop *payload* when its hash is already in the gate's executed
    ledger. Returns ``(payload_or_empty, executed_already)``.
    """
    if not payload:
        return [], []
    from .guards import hash_tool_calls
    signature = hash_tool_calls(payload)
    history = gate.get(GATE_EXECUTED_TOOL_CALLS_SIGNATURES) or []
    acked = gate.get(GATE_PENDING_CALLS_ACKED_SIGNATURE) or ""
    if signature and (signature in history or signature == acked):
        return [], [signature]
    return list(payload), []


def stamp_reentry_metadata(result: dict, gate: dict) -> None:
    """Mutate *result* in-place: attach ``reentry_cycle`` and
    ``reentry_instruction`` when the gate's reentry counter > 0.

    Both keys stay absent when the count is 0 so envelopes that never
    re-entered the stale-doc loop look identical to a fresh run.
    """
    reentry_cycle = int(gate.get(GATE_REENTRY_COUNT, 0) or 0)
    if reentry_cycle <= 0:
        return
    max_cycles = int(
        gate.get(GATE_MAX_CYCLES, DEFAULT_MAX_FIX_CYCLES)
        or DEFAULT_MAX_FIX_CYCLES
    )
    result[GATE_REENTRY_CYCLE] = reentry_cycle
    result[GATE_REENTRY_INSTRUCTION] = (
        f"You are in stale-doc re-entry cycle {reentry_cycle} of "
        f"{max_cycles}; this is the {ordinal(reentry_cycle)} automated "
        "re-review pass before the gate hard-blocks."
    )
