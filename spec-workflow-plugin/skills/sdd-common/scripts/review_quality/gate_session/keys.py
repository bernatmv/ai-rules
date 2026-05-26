"""Gate-session field-name constants.

Single source of truth for the dict-key vocabulary used by callers that
read or write the ``review_gate`` mapping. Module-level constants keep
typo regressions out of CI: a misspelt ``"pending_tool_calls"`` becomes
a name-error at import time instead of a silently-missing dict key.

Pair with :mod:`review_quality.gate_session.types` — the dataclass owns
the schema, this module owns the canonical key names emitters and
readers reach for when working with the dict view.
"""
from __future__ import annotations

# Session-level keys — top-level fields on the gate-session.json shape.
GATE_REVIEW_GATE = "review_gate"
GATE_LAUNCH_ARGS_CACHE = "launch_args_cache"

# Gate-level keys — fields on the inner ``review_gate`` mapping.
GATE_PENDING_CALLS = "pending_tool_calls"
GATE_PENDING_CALLS_SIGNATURE = "pending_tool_calls_signature"
GATE_PENDING_CALLS_ACKED_SIGNATURE = "pending_tool_calls_acked_signature"
GATE_EXECUTED_TOOL_CALLS_SIGNATURES = "executed_tool_calls_signatures"
GATE_LAUNCH_FLAGS = "launch_flags"
GATE_FIX_CYCLE = "fix_cycle"
GATE_MAX_CYCLES = "max_cycles"
GATE_REENTRY_COUNT = "reentry_count"

# Envelope-level keys — surfaced on phase response payloads.
GATE_REENTRY_CYCLE = "reentry_cycle"
GATE_REENTRY_INSTRUCTION = "reentry_instruction"

__all__ = [
    "GATE_REVIEW_GATE",
    "GATE_LAUNCH_ARGS_CACHE",
    "GATE_PENDING_CALLS",
    "GATE_PENDING_CALLS_SIGNATURE",
    "GATE_PENDING_CALLS_ACKED_SIGNATURE",
    "GATE_EXECUTED_TOOL_CALLS_SIGNATURES",
    "GATE_LAUNCH_FLAGS",
    "GATE_FIX_CYCLE",
    "GATE_MAX_CYCLES",
    "GATE_REENTRY_COUNT",
    "GATE_REENTRY_CYCLE",
    "GATE_REENTRY_INSTRUCTION",
]
