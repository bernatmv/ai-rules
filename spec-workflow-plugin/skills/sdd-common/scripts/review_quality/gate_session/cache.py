"""Phase-snapshot cache keys + artifact hashing for replay.

Typed snapshot contract: :func:`set_phase_snapshot` takes a
:class:`~review.snapshots.PhaseSnapshotBase` subclass and
:func:`get_phase_snapshot` rebuilds the subclass via
:meth:`cls.from_dict`. No untyped / flat-dict fallback exists — the
subclass is the single authority for the persisted shape.
"""
from __future__ import annotations

import os

from sdd_core.reference_ledger import hash_file
from sdd_core.time import ts_now

from review.snapshots import PhaseSnapshotBase

__all__ = [
    "hash_quality_artifact",
    "phase_cache_key",
    "get_phase_snapshot",
    "set_phase_snapshot",
]


def hash_quality_artifact(
    category: str, target_name: str, project_path: str = ".",
) -> str:
    """Return a short sha256 digest of the review-quality.json artifact.

    Used as an input to :func:`phase_cache_key`. The digest is short (16
    hex chars) because collisions within a single gate session are
    practically impossible and the key travels in the session file.
    Missing artifacts hash to the sentinel ``"<missing>"`` so the key
    function stays total.

    Delegates to :func:`sdd_core.reference_ledger.hash_file` — single
    read-in-chunks SHA-256 implementation for the whole skill.
    """
    from sdd_core.paths import doc_dir_path
    path = os.path.join(
        doc_dir_path(category, target_name, project_path),
        "review-quality.json",
    )
    return hash_file(
        path, limit_hex_chars=16, missing_sentinel="<missing>",
    )


def phase_cache_key(
    *, phase: str, artifact_hash: str, scope: str,
    fix_cycle: int, doc_list: str,
) -> str:
    """Deterministic cache key for :data:`phase_snapshots`.

    Every input that drives the routing shape feeds the key: ``phase``
    (post-review vs post-fix), ``artifact_hash`` (so re-reviews with new
    findings invalidate the slot), ``scope`` / ``doc_list`` (per-document
    vs final scopes never collide), and ``fix_cycle`` (cycle 0 vs cycle 1
    findings differ even when artifact hash matches mid-fix-loop).
    """
    return f"{phase}|{artifact_hash}|{scope}|{fix_cycle}|{doc_list}"


def _snapshot_frame(snapshot: PhaseSnapshotBase) -> dict:
    """Build the persisted frame for *snapshot*.

    Pure (no I/O) so tests can assert the frame shape without touching
    a session file. ``set_phase_snapshot`` is responsible only for
    mutating the session dict.
    """
    raw = snapshot.to_dict()
    return {
        "key": raw.get("key", ""),
        "inputs": raw,
        "taken_at": ts_now(),
    }


def get_phase_snapshot(
    session: dict, phase: str, *, cls: type[PhaseSnapshotBase],
) -> PhaseSnapshotBase | None:
    """Return the stored snapshot for *phase* rebuilt as *cls*.

    ``cls`` is required — single-authority for the persisted shape.
    Returns ``None`` when no snapshot exists for the phase.
    """
    snapshots = session.get("phase_snapshots") or {}
    snap = snapshots.get(phase)
    if not isinstance(snap, dict):
        return None
    inputs = snap.get("inputs") or {}
    raw = dict(inputs)
    raw.setdefault("key", snap.get("key", ""))
    return cls.from_dict(raw)


def set_phase_snapshot(
    session: dict, snapshot: PhaseSnapshotBase,
) -> None:
    """Persist the typed *snapshot* under its :attr:`phase_name`.

    Snapshots are :class:`~review.snapshots.PhaseSnapshotBase`
    subclasses; :meth:`snapshot.to_dict` yields a JSON-serialisable
    dict so the session survives a round trip through
    :func:`write_session`.
    """
    phase_name = snapshot.phase_name
    if not phase_name:
        raise ValueError(
            "set_phase_snapshot: snapshot.phase_name must be non-empty"
        )
    session.setdefault("phase_snapshots", {})[phase_name] = _snapshot_frame(
        snapshot,
    )
