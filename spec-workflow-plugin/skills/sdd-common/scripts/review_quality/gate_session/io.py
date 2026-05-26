"""Persistence primitives for the review gate-session file.

Canonical location: ``<doc_dir>/.sdd-state/gate-session.json``
(see ``sdd_core.transient_state``). Defaults + atomic read/write live
here so lifecycle and cache modules can focus on policy rather than on
how the bytes land on disk. ``.sdd-state/`` is the sole contract; any
other on-disk artefact is ignored and treated as a fresh session.
"""
from __future__ import annotations

import os
from typing import Set, Tuple

from sdd_core import output, transient_state
from sdd_core.time import ts_now
from ..constants import DEFAULT_MAX_FIX_CYCLES, SCOPE_PER_DOCUMENT

__all__ = [
    "session_path",
    "read_session",
    "write_session",
    "delete_session",
    "_default_session",
    "_default_review_gate",
    "_SESSION_FILENAME",
    "_SESSION_SCHEMA_VERSION",
    "_reset_banner_cache_for_tests",
]


# Process-local banner dedup — one emission per (category, target_name,
# project_path, reason) across all ``read_session`` callers in this
# process. The producer of the banner owns the dedup so no caller has
# to remember a ``quiet_missing`` flag.
_BANNER_EMITTED: Set[Tuple[str, str, str, str]] = set()


def _reset_banner_cache_for_tests() -> None:
    """Test-only reset hook for the in-process banner dedup set."""
    _BANNER_EMITTED.clear()


def _emit_missing_banner_once(
    path: str, category: str, target_name: str,
    project_path: str, reason: str,
) -> None:
    """Emit the "No gate session" INFO banner at most once per key."""
    key = (category, target_name, project_path, reason)
    if key in _BANNER_EMITTED:
        return
    _BANNER_EMITTED.add(key)
    output.info(f"No gate session at {path} — using fresh defaults")


_SESSION_SCHEMA_VERSION = "1.0.0"
# Canonical filename inside ``.sdd-state/``. Kept module-private under
# the leading-underscore name to preserve the existing import surface
# (``_SESSION_FILENAME`` is re-exported from the package ``__init__``).
_SESSION_FILENAME = transient_state.GATE_SESSION_FILENAME


def _default_review_gate(
    *, gate_id=None, parent_todo_id=None,
    parent_todo_content=None, max_cycles=DEFAULT_MAX_FIX_CYCLES,
    gate_uuid=None,
) -> dict:
    return {
        "gate_id": gate_id,
        # Server-generated handle the ``pipeline/tick`` dispatcher
        # uses to resolve a session without agent-typed flags.
        "gate_uuid": gate_uuid,
        "parent_todo_id": parent_todo_id,
        # Preserved across phases; consumed by ``compute_todo_payload``.
        "parent_todo_content": parent_todo_content,
        "fix_cycle": 0,
        # Stale-doc re-entry counter — bumped by ``pre_approval`` when
        # docs were modified after their last review. Kept separate
        # from ``fix_cycle`` so the bounded fix-loop contract
        # (``max_fix_cycles``) stays literal.
        "reentry_count": 0,
        "max_cycles": max_cycles,
        "current_state": None,
        "required_next_phase": None,
        "review_scope": SCOPE_PER_DOCUMENT,
        "active_todos": [],
        "pending_tool_calls": [],
        "executed_tool_calls_signatures": [],
        "terminal_state": None,
        "terminal_reason": None,
        "user_accepted_at": None,
    }


def _default_session() -> dict:
    return {
        "schema_version": _SESSION_SCHEMA_VERSION,
        "category": None,
        "target_name": None,
        "workflow_mode": None,
        "current_step": None,
        "completed_gates": [],
        "started_at": None,
        "updated_at": None,
        "review_gate": _default_review_gate(),
        "launch_args_cache": {},
        # Idempotency cache for terminal-output-truncation replay.
        # One slot per phase name; each stores a cache key + input
        # snapshot so a second call with identical inputs replays the
        # routing instead of triggering a sequence violation on the
        # advanced required_next_phase.
        "phase_snapshots": {},
        # Carries across ``complete_gate`` so a later ``--phase
        # launch`` can prompt the agent (via ``AskQuestion``) to
        # confirm whether the single-document early stop was
        # intentional. ``None`` when no marker is active.
        "single_doc_stop_marker": None,
    }


def session_path(category: str, target_name: str, project_path: str = "") -> str:
    """Return canonical gate-session.json path (under ``.sdd-state/``)."""
    return transient_state.state_path(
        category, target_name, _SESSION_FILENAME, project_path,
    )


def read_session(
    category: str, target_name: str, project_path: str = "",
    *, quiet_missing: bool = False,
) -> dict:
    """Read session, returning defaults if file absent.

    Reads only the canonical ``.sdd-state/`` path; an absent or
    malformed file returns a fresh default session.

    ``quiet_missing=True`` suppresses the stderr INFO line entirely —
    use when the caller *knows* absence is expected (e.g. the
    ``complete`` phase post-cleanup, or the dispatcher's read-only
    routing tick). When ``quiet_missing=False`` the banner is still
    emitted at most once per ``(category, target_name, project_path,
    reason)`` key within the current process, so multiple downstream
    read call sites never produce a chorus.
    """
    path = session_path(category, target_name, project_path)
    if not os.path.exists(path):
        if not quiet_missing:
            _emit_missing_banner_once(
                path, category, target_name, project_path, "missing",
            )
        return _default_session()
    data = output.safe_read_json(path, default=None)
    if data is None or not isinstance(data, dict):
        if not quiet_missing:
            _emit_missing_banner_once(
                path, category, target_name, project_path, "malformed",
            )
        return _default_session()
    result = _default_session()
    for key in result:
        if key in data:
            result[key] = data[key]
    if not result.get("workflow_mode"):
        result["workflow_mode"] = "create"
    rg = result.get("review_gate")
    if not rg or not isinstance(rg, dict):
        result["review_gate"] = _default_review_gate()
    else:
        defaults = _default_review_gate()
        for k in defaults:
            if k not in rg:
                rg[k] = defaults[k]
    return result


def write_session(
    category: str, target_name: str, session_data: dict,
    project_path: str = "",
) -> None:
    """Atomic-write session to disk, auto-setting updated_at.

    Mutates session_data in place (sets updated_at). Writes go to the
    canonical ``.sdd-state/`` location.
    """
    session_data["updated_at"] = ts_now()
    path = session_path(category, target_name, project_path)
    transient_state.ensure_state_dir(category, target_name, project_path)
    output.atomic_write_json(path, session_data)


def delete_session(category: str, target_name: str, project_path: str = "") -> bool:
    """Delete session file. Returns True if any file was deleted."""
    path = session_path(category, target_name, project_path)
    try:
        os.unlink(path)
        return True
    except FileNotFoundError:
        return False
