"""Single source of truth for cross-phase pre-flight advisory state."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final, Iterable, Mapping

from sdd_core import output, paths
from sdd_core.time import ts_now

__all__ = [
    "PREFLIGHT_STATE_FILENAME",
    "SCHEMA_VERSION",
    "PreflightAdvisoryRow",
    "ResolveOutcome",
    "state_path",
    "persist",
    "load",
    "mark_resolved",
    "gate_on_unresolved_advisories",
]

PREFLIGHT_STATE_FILENAME: Final[str] = "preflight.json"
SCHEMA_VERSION: Final[int] = 1


@dataclass(frozen=True)
class ResolveOutcome:
    """Result of :func:`mark_resolved`.

    ``mutated`` true when one or more advisories flipped to resolved.
    ``missing_file`` true when the state file does not exist on disk.
    ``unknown_name`` true when the file exists but the name is absent.
    ``already_resolved`` true when the named advisory was found but
    every matching row was already resolved (no mutation, but the name
    is not "unknown").
    """

    mutated: bool
    missing_file: bool = False
    unknown_name: bool = False
    already_resolved: bool = False


@dataclass(frozen=True)
class PreflightAdvisoryRow:
    name: str
    action_required: bool
    next_action_command: str
    resolved: bool = False
    detected_at: str = ""
    resolved_at: str = ""
    hint: str = ""
    session_id: str = ""

    def to_dict(self) -> dict:
        payload: dict = {
            "name": self.name,
            "action_required": self.action_required,
            "next_action_command": self.next_action_command,
            "resolved": self.resolved,
            "detected_at": self.detected_at,
            "resolved_at": self.resolved_at,
            "hint": self.hint,
        }
        if self.session_id:
            payload["session_id"] = self.session_id
        return payload


def state_path(workspace: str = "") -> str:
    return paths.workflow_state_path(PREFLIGHT_STATE_FILENAME, workspace)


def _coerce_row(raw: Mapping) -> PreflightAdvisoryRow | None:
    name = str(raw.get("name") or "")
    if not name:
        return None
    return PreflightAdvisoryRow(
        name=name,
        action_required=bool(raw.get("action_required", False)),
        next_action_command=str(raw.get("next_action_command") or ""),
        resolved=bool(raw.get("resolved", False)),
        detected_at=str(raw.get("detected_at") or ts_now()),
        resolved_at=str(raw.get("resolved_at") or ""),
        hint=str(raw.get("hint") or raw.get("banner") or raw.get("detail") or ""),
        session_id=str(raw.get("session_id") or ""),
    )


def _explicit_resolution(raw: Mapping) -> bool:
    """Return True when the incoming row explicitly carries resolution state.

    The merge path uses this to decide whether to honour the new row's
    ``resolved``/``resolved_at``/``session_id`` or carry forward the
    prior on-disk values. Absence of all three means the caller did not
    set them — typical for a re-detection pass that should not flip a
    previously-resolved bit back to false.
    """
    return any(
        raw.get(key) not in (None, "", False)
        for key in ("resolved", "resolved_at", "session_id")
    )


def persist(advisories: Iterable[Mapping], *, workspace: str = "") -> None:
    """Persist advisory rows, merging with prior on-disk state.

    For each new advisory matched by ``name`` against an existing row,
    carry forward ``resolved``, ``resolved_at``, and ``session_id``
    unless the new row explicitly sets them. This keeps a re-detection
    pass from wiping a resolution that was just recorded by a sibling
    command (e.g. ``resolve-advisory.py``).

    Rows present on disk but absent from the new batch are dropped:
    the new batch is the canonical view of currently-detected
    advisories; resolved-but-still-detected rows are merged through,
    while resolved-and-no-longer-detected rows fall away naturally.
    """
    path = state_path(workspace)
    prior_raw = output.safe_read_json(path, default={})
    prior_rows: dict[str, dict] = {}
    if isinstance(prior_raw, dict):
        for item in prior_raw.get("advisories") or []:
            if isinstance(item, Mapping):
                pname = str(item.get("name") or "")
                if pname:
                    prior_rows[pname] = dict(item)

    merged: list[dict] = []
    for advisory in advisories or []:
        if not isinstance(advisory, Mapping):
            continue
        row = _coerce_row(advisory)
        if row is None:
            continue
        as_dict = row.to_dict()
        prior = prior_rows.get(row.name)
        if prior is not None and not _explicit_resolution(advisory):
            if prior.get("resolved"):
                as_dict["resolved"] = True
            prior_resolved_at = prior.get("resolved_at")
            if prior_resolved_at and not as_dict.get("resolved_at"):
                as_dict["resolved_at"] = str(prior_resolved_at)
            prior_session = prior.get("session_id")
            if prior_session and not as_dict.get("session_id"):
                as_dict["session_id"] = str(prior_session)
        merged.append(as_dict)

    output.atomic_write_json(
        path,
        {
            "schema_version": SCHEMA_VERSION,
            "updated_at": ts_now(),
            "advisories": merged,
        },
    )


def load(*, workspace: str = "") -> list[PreflightAdvisoryRow]:
    raw = output.safe_read_json(state_path(workspace), default={})
    if not isinstance(raw, dict):
        return []
    rows = raw.get("advisories")
    if not isinstance(rows, list):
        return []
    out = []
    for item in rows:
        if isinstance(item, Mapping):
            row = _coerce_row(item)
            if row is not None:
                out.append(row)
    return out


def mark_resolved(
    name: str,
    *,
    workspace: str = "",
    session_id: str = "",
) -> ResolveOutcome:
    """Flip the named advisory to resolved on disk.

    When ``session_id`` is non-empty it is stamped on the row alongside
    ``resolved_at``. The session id pins the resolution to one harness
    process so re-detection in the same session can short-circuit while
    a fresh process (fresh session) still re-fires.
    """
    path = state_path(workspace)
    if not Path(path).is_file():
        return ResolveOutcome(mutated=False, missing_file=True)
    raw = output.safe_read_json(path, default={})
    if not isinstance(raw, dict):
        return ResolveOutcome(mutated=False, unknown_name=True)
    rows = raw.get("advisories")
    if not isinstance(rows, list):
        return ResolveOutcome(mutated=False, unknown_name=True)
    mutated = False
    found = False
    for item in rows:
        if not isinstance(item, dict):
            continue
        if item.get("name") != name:
            continue
        found = True
        if item.get("resolved"):
            continue
        item["resolved"] = True
        item["resolved_at"] = ts_now()
        if session_id:
            item["session_id"] = session_id
        mutated = True
    if mutated:
        raw["updated_at"] = ts_now()
        output.atomic_write_json(path, raw)
        return ResolveOutcome(mutated=True)
    if found:
        return ResolveOutcome(mutated=False, already_resolved=True)
    return ResolveOutcome(mutated=False, unknown_name=True)


def gate_on_unresolved_advisories(*, workspace: str = "") -> None:
    blocking = [
        row for row in load(workspace=workspace)
        if row.action_required and not row.resolved
    ]
    if not blocking:
        return
    first = blocking[0]
    output.preflight_required(
        {
            "blocking_advisories": [row.name for row in blocking],
            "first_blocking": first.to_dict(),
            "workspace": workspace or ".",
        },
        f"Pre-flight advisory unresolved: {first.name}",
        next_action_command=first.next_action_command,
        hint=first.hint or f"Run: {first.next_action_command}",
        error=f"{len(blocking)} advisory/advisories require resolution",
    )
