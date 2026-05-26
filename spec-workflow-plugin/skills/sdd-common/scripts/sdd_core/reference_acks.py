"""Project-scoped reference-acknowledgement ledger.

Stores one ``reference-acks.json`` per checkout, keyed on
``(absolute_path, sha256, gate_id)``. Renamed references miss (force a
read); a changed content hash re-demands a read.

Path: ``<project>/.spec-workflow/.sdd-state/reference-acks.json``.

Resolution order (first hit wins):
- workspace ledger
- per-repo project ledger
- per-repo siblings on the workspace tracker
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Final, Optional

from sdd_core import paths
from sdd_core.time import ts_now

__all__ = [
    "REFERENCE_ACKS_FILENAME",
    "SCHEMA_VERSION",
    "GLOBAL_GATE_ID",
    "ReferenceAckEntry",
    "acks_path",
    "is_acked",
    "record_ack",
    "load_entries",
    "reset",
]


SCHEMA_VERSION: Final[int] = 2
REFERENCE_ACKS_FILENAME: Final[str] = "reference-acks.json"
GLOBAL_GATE_ID: Final[str] = "__global__"


@dataclass(frozen=True)
class ReferenceAckEntry:
    abs_path: str
    sha256: str
    first_ack_at: str
    last_seen_at: str
    gate_id: str = GLOBAL_GATE_ID

    def to_dict(self) -> dict:
        return {
            "abs_path": self.abs_path,
            "sha256": self.sha256,
            "first_ack_at": self.first_ack_at,
            "last_seen_at": self.last_seen_at,
            "gate_id": self.gate_id,
        }


def acks_path(project_path: str = "") -> str:
    """Resolve ``reference-acks.json`` under ``<project>/.spec-workflow/.sdd-state/``.

    Routes through :func:`sdd_core.paths.workflow_state_path` so the
    ledger location stays in lock-step with every other cross-cutting
    state file (``harness.json``, ``deferred-tool-preload.json``).
    No inline ``.sdd-state`` literal — single owner is
    :data:`sdd_core.paths.STATE_DIR_NAME`.
    """
    return paths.workflow_state_path(REFERENCE_ACKS_FILENAME, project_path)


def workspace_acks_path(workspace_root: str) -> str:
    """Resolve the workspace-scoped ledger path.

    Lives at ``<workspace>/.spec-workflow/.sdd-state/reference-acks.json``.
    The workspace ledger is the *primary* surface when a tracker is
    reachable — per-repo files keep being written for one minor version
    so callers mid-flight do not re-arm preconditions on rollback.
    """
    return str(paths.workspace_state_dir(workspace_root) / REFERENCE_ACKS_FILENAME)


def _ensure_parent(path: str) -> None:
    Path(os.path.dirname(path)).mkdir(parents=True, exist_ok=True)


def _normalise(data) -> dict:
    """Coerce *data* into the canonical ``{schema_version, acks}`` shape."""
    if not isinstance(data, dict):
        return {"schema_version": SCHEMA_VERSION, "acks": []}
    data.setdefault("schema_version", SCHEMA_VERSION)
    acks = data.get("acks")
    if not isinstance(acks, list):
        data["acks"] = []
    return data


def _read_raw(path: str) -> dict:
    if not os.path.isfile(path):
        return {"schema_version": SCHEMA_VERSION, "acks": []}
    try:
        with open(path, encoding="utf-8") as f:
            return _normalise(json.load(f))
    except (OSError, json.JSONDecodeError):
        return {"schema_version": SCHEMA_VERSION, "acks": []}


def _entries_from_ack_list(raw_acks: list) -> list[ReferenceAckEntry]:
    """Parse a raw ``acks`` list into validated :class:`ReferenceAckEntry`.

    Single owner of the dict→dataclass projection; both the per-repo
    and workspace-scoped readers route through here so a schema add
    lands in one place.
    """
    out: list[ReferenceAckEntry] = []
    for entry in raw_acks or []:
        if not isinstance(entry, dict):
            continue
        abs_path = entry.get("abs_path")
        sha = entry.get("sha256")
        if not isinstance(abs_path, str) or not isinstance(sha, str):
            continue
        out.append(
            ReferenceAckEntry(
                abs_path=abs_path,
                sha256=sha,
                first_ack_at=entry.get("first_ack_at") or "",
                last_seen_at=entry.get("last_seen_at") or "",
                gate_id=entry.get("gate_id") or GLOBAL_GATE_ID,
            )
        )
    return out


def load_entries(project_path: str = "") -> list[ReferenceAckEntry]:
    """Return every entry currently in the ledger (latest-write wins)."""
    data = _read_raw(acks_path(project_path))
    return _entries_from_ack_list(data["acks"])


def is_acked(
    abs_path: str,
    sha256: str,
    *,
    project_path: str = "",
    gate_id: str = GLOBAL_GATE_ID,
    max_age: "timedelta | None" = None,
    now: "datetime | None" = None,
) -> bool:
    """Return True when a visible ledger contains a fresh gate-scoped ack.

    Walks the workspace ledger first (one ack satisfies every sibling
    repo by name+sha256), then the per-repo ledger (absolute-path
    match), then per-repo siblings on the workspace tracker for the
    compatibility window.
    """
    if not abs_path or not sha256:
        return False
    normalised = os.path.abspath(abs_path)
    reference_name = os.path.basename(abs_path)
    gate = gate_id or GLOBAL_GATE_ID

    workspace_root = paths.find_workspace_tracker_root(project_path)
    if workspace_root:
        for entry in _load_workspace_entries(workspace_root):
            if _entry_matches_policy(
                entry, gate_id=gate, max_age=max_age, now=now,
            ) and entry.sha256 == sha256 and (
                os.path.basename(entry.abs_path) == reference_name
                or entry.abs_path == reference_name
            ):
                return True

    for entry in load_entries(project_path):
        if (
            _entry_matches_policy(
                entry, gate_id=gate, max_age=max_age, now=now,
            )
            and entry.abs_path == normalised
            and entry.sha256 == sha256
        ):
            return True

    if not workspace_root:
        return False
    return _is_acked_in_workspace(
        reference_name=reference_name, sha256=sha256,
        workspace_root=workspace_root, gate_id=gate,
        max_age=max_age, now=now,
    )


def _parse_timestamp(raw: str) -> "datetime | None":
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _entry_matches_policy(
    entry: ReferenceAckEntry,
    *,
    gate_id: str,
    max_age: "timedelta | None",
    now: "datetime | None",
) -> bool:
    if entry.gate_id != gate_id:
        return False
    if max_age is None:
        return True
    if max_age <= timedelta(0):
        return False
    last_seen = _parse_timestamp(entry.last_seen_at)
    if last_seen is None:
        return False
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current - last_seen <= max_age


def _load_workspace_entries(workspace_root: str) -> list[ReferenceAckEntry]:
    """Read the workspace-scoped ledger; absent file → empty list."""
    path = workspace_acks_path(workspace_root)
    raw = _read_raw(path)
    return _entries_from_ack_list(raw["acks"])


def _is_acked_in_workspace(
    *,
    reference_name: str,
    sha256: str,
    workspace_root: str,
    gate_id: str,
    max_age: "timedelta | None",
    now: "datetime | None",
) -> bool:
    """Walk every sibling repo on the workspace tracker."""
    if not reference_name or not sha256:
        return False
    for repo in _workspace_repo_paths(workspace_root):
        for entry in load_entries(repo):
            if (
                _entry_matches_policy(
                    entry, gate_id=gate_id, max_age=max_age, now=now,
                )
                and os.path.basename(entry.abs_path) == reference_name
                and entry.sha256 == sha256
            ):
                return True
    return False


def _workspace_repo_paths(workspace_root: str) -> list[str]:
    """Return the per-repo paths declared on every workspace tracker.

    Thin adapter over :func:`workspace_tracker.iter_workspace_repo_roots`
    so the resolution rules (repo-path resolution, dedupe, schema-warning
    suppression) live in one place.
    """
    from sdd_core import workspace_tracker
    return [str(p) for p in workspace_tracker.iter_workspace_repo_roots(workspace_root)]


def _merge_ack_into_store(
    path: str,
    *,
    normalised_abs: str,
    sha256: str,
    now: str,
    gate_id: str,
) -> "ReferenceAckEntry | None":
    """Locate-or-append a single ack row inside the store at ``path``.

    Caller still owns store-level transactionality. Returns the merged
    entry on the per-repo branch so the caller can echo it; returns
    ``None`` on the workspace branch where the value is unused.
    """
    from sdd_core.security.state import TransactionalStore

    _ensure_parent(path)
    with TransactionalStore(path) as store:
        raw = store.read_json(
            default={"schema_version": SCHEMA_VERSION, "acks": []},
        )
        data = _normalise(raw)
        for entry in data["acks"]:
            if (
                entry.get("abs_path") == normalised_abs
                and entry.get("sha256") == sha256
                and (entry.get("gate_id") or GLOBAL_GATE_ID) == gate_id
            ):
                entry["last_seen_at"] = now
                entry["gate_id"] = gate_id
                data["schema_version"] = SCHEMA_VERSION
                store.write_json(data)
                return ReferenceAckEntry(
                    abs_path=normalised_abs,
                    sha256=sha256,
                    first_ack_at=entry.get("first_ack_at") or now,
                    last_seen_at=now,
                    gate_id=gate_id,
                )
        new = {
            "abs_path": normalised_abs,
            "sha256": sha256,
            "first_ack_at": now,
            "last_seen_at": now,
            "gate_id": gate_id,
        }
        data["acks"].append(new)
        data["schema_version"] = SCHEMA_VERSION
        store.write_json(data)
    return ReferenceAckEntry(**new)


def record_ack(
    abs_path: str,
    sha256: str,
    *,
    project_path: str = "",
    gate_id: str = GLOBAL_GATE_ID,
) -> ReferenceAckEntry:
    """Append or refresh a ``(abs_path, sha256)`` entry.

    When *project_path* is inside a workspace the workspace-scoped
    ledger receives the canonical write so any sibling repo can satisfy
    the precondition by name+sha256 alone. The per-repo write remains
    for the compatibility window so older callers that still consult the
    project ledger directly stay coherent.
    """
    from sdd_core.output import _dry_run_active

    if _dry_run_active():
        # Dry-run contract: never touch disk. Return a synthetic entry
        # so callers can still reason about the happy-path shape.
        now = ts_now()
        return ReferenceAckEntry(
            abs_path=os.path.abspath(abs_path),
            sha256=sha256,
            first_ack_at=now,
            last_seen_at=now,
            gate_id=gate_id or GLOBAL_GATE_ID,
        )

    normalised = os.path.abspath(abs_path)
    now = ts_now()
    gate = gate_id or GLOBAL_GATE_ID

    workspace_root = paths.find_workspace_tracker_root(project_path)
    if workspace_root:
        _merge_ack_into_store(
            workspace_acks_path(workspace_root),
            normalised_abs=normalised, sha256=sha256, now=now,
            gate_id=gate,
        )

    entry = _merge_ack_into_store(
        acks_path(project_path),
        normalised_abs=normalised, sha256=sha256, now=now,
        gate_id=gate,
    )
    assert entry is not None  # the per-repo branch always returns an entry
    return entry


def reset(project_path: str = "") -> Optional[str]:
    """Remove the ledger file; returns the deleted path (or ``None``)."""
    path = acks_path(project_path)
    if not os.path.isfile(path):
        return None
    try:
        os.unlink(path)
    except OSError:
        return None
    return path
