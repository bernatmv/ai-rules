"""Gate session I/O — read/write gate-session.json for review gate state.

Single-responsibility package for gate session persistence (SRP): a
standalone session file co-located with reviewed documents holds the
review gate state.

Session file locations (all under ``.sdd-state/``):
  - Steering:  .spec-workflow/steering/.sdd-state/gate-session.json
  - Spec:      .spec-workflow/specs/{name}/.sdd-state/gate-session.json
  - Discovery: .spec-workflow/discovery/{name}/.sdd-state/gate-session.json

Submodule layout (import-stable facade):
  * ``io``        — atomic read/write, defaults, delete.
  * ``lifecycle`` — init, stale detection, gate advancement.
  * ``cache``     — phase snapshots + artifact hashing.
"""
from __future__ import annotations

from .cache import (
    get_phase_snapshot,
    hash_quality_artifact,
    phase_cache_key,
    set_phase_snapshot,
)
from .io import (
    _SESSION_FILENAME,
    _SESSION_SCHEMA_VERSION,
    _default_review_gate,
    _default_session,
    _reset_banner_cache_for_tests,
    delete_session,
    read_session,
    session_path,
    write_session,
)
from .lifecycle import (
    advance_gate,
    complete_gate,
    detect_stale_entry,
    get_user_accept_time,
    init_session,
    record_executed_signature,
    record_user_accept,
)
from .keys import (
    GATE_EXECUTED_TOOL_CALLS_SIGNATURES,
    GATE_FIX_CYCLE,
    GATE_LAUNCH_ARGS_CACHE,
    GATE_LAUNCH_FLAGS,
    GATE_MAX_CYCLES,
    GATE_PENDING_CALLS,
    GATE_PENDING_CALLS_ACKED_SIGNATURE,
    GATE_PENDING_CALLS_SIGNATURE,
    GATE_REENTRY_COUNT,
    GATE_REENTRY_CYCLE,
    GATE_REENTRY_INSTRUCTION,
    GATE_REVIEW_GATE,
)
from .types import (
    GateSession,
    PhaseSnapshot,
    Todo,
    WorkflowSession,
)

__all__ = [
    "session_path",
    "read_session",
    "write_session",
    "delete_session",
    "init_session",
    "detect_stale_entry",
    "record_user_accept",
    "get_user_accept_time",
    "advance_gate",
    "complete_gate",
    "record_executed_signature",
    "hash_quality_artifact",
    "phase_cache_key",
    "get_phase_snapshot",
    "set_phase_snapshot",
    # Typed views (see types.py):
    "WorkflowSession",
    "GateSession",
    "PhaseSnapshot",
    "Todo",
    # Gate-state key constants (see keys.py):
    "GATE_EXECUTED_TOOL_CALLS_SIGNATURES",
    "GATE_FIX_CYCLE",
    "GATE_LAUNCH_ARGS_CACHE",
    "GATE_LAUNCH_FLAGS",
    "GATE_MAX_CYCLES",
    "GATE_PENDING_CALLS",
    "GATE_PENDING_CALLS_ACKED_SIGNATURE",
    "GATE_PENDING_CALLS_SIGNATURE",
    "GATE_REENTRY_COUNT",
    "GATE_REENTRY_CYCLE",
    "GATE_REENTRY_INSTRUCTION",
    "GATE_REVIEW_GATE",
]
