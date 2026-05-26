"""Workspace-scoped session token.

A session id is minted on first use per workspace and persisted under
``<workspace_root>/.spec-workflow/.sdd-state/session-<epoch_ms>.json``
so sibling subprocesses share one token. The token survives across
processes; rotation is explicit (delete the session file or call
:func:`_reset_cache_for_tests`), not tied to process lifetime.
The on-disk file exposes ``{session_id, epoch_ms, created_at}``;
read-only callers pull the active session via
:func:`current_session_id`.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from sdd_core import output
from sdd_core.paths import STATE_DIR_NAME, WORKFLOW_DIR
from sdd_core.time import ts_now

__all__ = [
    "get_or_create_session_id",
    "current_session_id",
    "current_session_epoch_ms",
    "session_file_path",
    "_reset_cache_for_tests",
]


# Process-local cache: workspace_root (resolved absolute string) → token.
# Tests can reset by re-importing this module fresh.
_SESSION_CACHE: dict[str, str] = {}


def _state_dir(workspace_root: Path) -> Path:
    return Path(workspace_root) / WORKFLOW_DIR / STATE_DIR_NAME


def _cache_key(workspace_root: Path) -> str:
    return str(Path(workspace_root).resolve())


def session_file_path(workspace_root: Path, epoch_ms: int) -> Path:
    """Return the canonical session file path for ``epoch_ms``."""
    return _state_dir(workspace_root) / f"session-{epoch_ms}.json"


def get_or_create_session_id(workspace_root: Path) -> str:
    """Return the active session token, creating one if needed.

    Resolution order:
      1. process-local cache,
      2. latest ``session-<epoch_ms>.json`` on disk,
      3. mint a fresh token and persist it.

    Step 2 is what lets sibling subprocesses share one session id —
    a fresh Python process attached to a workspace that already holds
    a session file rejoins that session instead of forking its own.
    """
    key = _cache_key(workspace_root)
    cached = _SESSION_CACHE.get(key)
    if cached is not None:
        return cached

    existing = current_session_id(workspace_root)
    if existing:
        _SESSION_CACHE[key] = existing
        return existing

    epoch_ms = int(time.time() * 1000)
    token = f"sess-{epoch_ms}-{os.getpid()}"
    state_dir = _state_dir(workspace_root)
    state_dir.mkdir(parents=True, exist_ok=True)
    path = session_file_path(workspace_root, epoch_ms)
    output.atomic_write_json(
        str(path),
        {
            "session_id": token,
            "epoch_ms": epoch_ms,
            "created_at": ts_now(),
        },
    )
    _SESSION_CACHE[key] = token
    return token


def _reset_cache_for_tests() -> None:
    """Drop the process-local session cache. Test-only seam.

    Simulates a fresh harness process: the next
    :func:`get_or_create_session_id` call will mint a new token and
    persist a new ``session-<epoch_ms>.json`` file even when the
    workspace already holds one from a prior session.
    """
    _SESSION_CACHE.clear()


def current_session_id(workspace_root: Path) -> str | None:
    """Return the session id from the most recent on-disk session file.

    Reader-only helper: never writes. Returns ``None`` when no session
    file is present. The "latest session" is shared by every process
    attached to this workspace until the file is removed.
    """
    raw = _read_latest_session_blob(workspace_root)
    if raw is None:
        return None
    token = raw.get("session_id")
    return str(token) if isinstance(token, str) and token else None


def current_session_epoch_ms(workspace_root: Path) -> int | None:
    """Return the active session's start epoch (milliseconds) or ``None``.

    Reads ``session-<epoch_ms>.json``'s ``epoch_ms`` field rather than
    parsing the filename so a future schema change owns the source of
    truth in one place.
    """
    raw = _read_latest_session_blob(workspace_root)
    if raw is None:
        return None
    epoch_ms = raw.get("epoch_ms")
    if isinstance(epoch_ms, bool):
        return None
    if isinstance(epoch_ms, int):
        return epoch_ms
    if isinstance(epoch_ms, float):
        return int(epoch_ms)
    return None


def _read_latest_session_blob(workspace_root: Path) -> dict[str, Any] | None:
    state_dir = _state_dir(workspace_root)
    if not state_dir.is_dir():
        return None
    candidates = sorted(state_dir.glob("session-*.json"))
    if not candidates:
        return None
    raw = output.safe_read_json(str(candidates[-1]), default=None)
    if isinstance(raw, dict):
        return raw
    return None
