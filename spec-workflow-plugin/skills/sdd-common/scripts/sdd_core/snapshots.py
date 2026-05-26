"""Snapshot creation, metadata management, and comparison."""
from __future__ import annotations

import difflib
import json
import uuid
from pathlib import Path

from .time import ts_now, ts_from_epoch
from .output import atomic_write_json
from .security import hasher, locked_store

__all__ = [
    "create_snapshot",
    "read_metadata",
    "get_next_version",
    "load_snapshot",
    "compare_snapshots",
    "iter_snapshot_files",
    "compute_canonical_path",
]


def create_snapshot(file_path: Path, approval_id: str, approval_title: str,
                    trigger: str, status: str, snapshots_base: Path,
                    canonical_path: str = "") -> dict:
    """Create a versioned snapshot. Returns snapshot metadata dict."""
    snapshots_base.mkdir(parents=True, exist_ok=True)
    version = get_next_version(snapshots_base)

    try:
        content = file_path.read_text()
        stat = file_path.stat()
    except FileNotFoundError:
        content, stat = "", None

    # Embed the content-hash so ``has_approved_snapshot`` can verify
    # identity without re-opening the source file — the snapshot
    # captures the bytes-at-record time verbatim. Hash via the seam so
    # a FIPS prescription that swaps the algorithm propagates here.
    content_hash = (
        f"{hasher().algo}:{hasher().hash_file(file_path)}"
        if content else f"{hasher().algo}:"
    )
    snapshot = {
        "id": f"snapshot_{uuid.uuid4().hex[:12]}",
        "approvalId": approval_id,
        "approvalTitle": approval_title,
        "version": version,
        "timestamp": ts_now(),
        "trigger": trigger,
        "status": status,
        "content": content,
        "canonicalPath": canonical_path,
        "contentHash": content_hash,
        "fileStats": {
            "size": stat.st_size if stat else 0,
            "lines": content.count("\n") + (1 if content else 0),
            "lastModified": ts_from_epoch(stat.st_mtime) if stat else ts_now()
        }
    }

    snap_file = snapshots_base / f"snapshot-{version:03d}.json"
    atomic_write_json(str(snap_file), snapshot)

    meta_file = snapshots_base / "metadata.json"
    with locked_store(meta_file) as store:
        meta = store.read_json(default={"snapshots": []})
        meta.setdefault("snapshots", []).append({
            "version": version,
            "timestamp": snapshot["timestamp"],
            "trigger": trigger,
            "approvalId": approval_id,
            "snapshotFile": snap_file.name,
        })
        meta["latestVersion"] = version
        store.write_json(meta)

    return snapshot


def read_metadata(snapshots_dir_path: Path) -> dict:
    """Read metadata.json from the snapshots directory, or return empty defaults."""
    meta_file = snapshots_dir_path / "metadata.json"
    if meta_file.exists():
        return json.loads(meta_file.read_text())
    return {"snapshots": [], "latestVersion": 0}


def get_next_version(snapshots_dir_path: Path) -> int:
    """Return the next sequential snapshot version number."""
    meta = read_metadata(snapshots_dir_path)
    return meta.get("latestVersion", 0) + 1


def load_snapshot(snapshots_dir_path: Path, version: int) -> dict:
    """Load a snapshot by version number. Raises ``FileNotFoundError`` if absent."""
    snap_file = snapshots_dir_path / f"snapshot-{version:03d}.json"
    if not snap_file.exists():
        raise FileNotFoundError(f"Snapshot version {version} not found at {snap_file}")
    return json.loads(snap_file.read_text())


def iter_snapshot_files(snapshots_dir_path: Path) -> list[Path]:
    """Return ``snapshot-NNN.json`` files in *snapshots_dir_path*, sorted by name.

    Excludes ``metadata.json`` and any non-snapshot siblings so callers
    walking legacy directories never need to filter the list themselves.
    """
    if not snapshots_dir_path.is_dir():
        return []
    return sorted(
        p for p in snapshots_dir_path.iterdir()
        if p.is_file() and p.name.startswith("snapshot-") and p.suffix == ".json"
    )


def compute_canonical_path(workflow_root: Path, spec_name: str, basename: str) -> str:
    """Compute the canonicalPath value for a snapshot under *spec_name*.

    Mirrors the absolute-path form ``approval/request.py`` records in
    ``approval_data["canonicalPath"]`` so the migrated snapshot matches
    what ``has_approved_snapshot`` looks up at read time. The live doc
    does not need to exist — callers that migrate stale snapshots still
    receive the path their gate would have produced when the doc was
    present.
    """
    # Compose against the documented spec directory layout. Importing
    # paths here would risk a cycle with the rest of sdd_core, so we
    # reproduce the small constant tuple inline.
    target = Path(workflow_root) / ".spec-workflow" / "specs" / spec_name / basename
    try:
        return str(target.resolve(strict=True))
    except FileNotFoundError:
        # Fall back to a non-strict resolve so migrating a snapshot for a
        # doc that has since been deleted still produces a stable value.
        return str(target.resolve())


def compare_snapshots(snapshots_dir_path: Path, version_a: int, version_b: int) -> dict:
    """Generate a unified diff between two snapshot versions."""
    snap_a = load_snapshot(snapshots_dir_path, version_a)
    snap_b = load_snapshot(snapshots_dir_path, version_b)

    lines_a = snap_a["content"].splitlines(keepends=True)
    lines_b = snap_b["content"].splitlines(keepends=True)
    diff = list(difflib.unified_diff(lines_a, lines_b, fromfile=f"v{version_a}", tofile=f"v{version_b}"))

    additions = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
    deletions = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))

    return {
        "snapshotA": {"version": version_a, "timestamp": snap_a["timestamp"]},
        "snapshotB": {"version": version_b, "timestamp": snap_b["timestamp"]},
        "summary": {"additions": additions, "deletions": deletions},
        "diff": "".join(diff)
    }
