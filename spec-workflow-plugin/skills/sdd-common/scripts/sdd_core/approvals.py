"""Approval JSON read/write/scan operations."""
from __future__ import annotations

import json
import os
import random
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Callable

from .output import atomic_write_json, warn as _output_warn
from .security.approval_record import ApprovalRecord, VerificationState

__all__ = [
    "VALID_STATUSES",
    "RESOLVED_STATUSES",
    "APPROVAL_CATEGORIES",
    "SnapshotValidationResult",
    "validate_approval_snapshot",
    "read_approval",
    "write_approval",
    "scan_approvals",
    "find_approval_by_id",
    "create_approval_id",
    "filter_by_age",
    "has_approved",
    "has_approved_snapshot",
    "has_approved_any",
    "has_approved_audit",
    "legacy_snapshot_migration_command",
]

VALID_STATUSES = frozenset({"pending", "approved", "rejected", "needs_revision"})
RESOLVED_STATUSES = frozenset({"approved", "rejected"})
APPROVAL_CATEGORIES = ("spec", "steering", "discovery")


class SnapshotValidationResult(Enum):
    VALID = "valid"
    HASH_MISMATCH = "hash_mismatch"
    LEGACY_MISSING_CANONICAL_PATH = "legacy_missing_canonical_path"
    PATH_MISMATCH = "path_mismatch"


def validate_approval_snapshot(
    body: dict,
    canonical_path: str,
    expected_hash_token: str,
) -> SnapshotValidationResult:
    """Classify a snapshot body against the caller's expected identity."""
    if (body.get("contentHash") or "") != expected_hash_token:
        return SnapshotValidationResult.HASH_MISMATCH
    if "canonicalPath" not in body:
        return SnapshotValidationResult.LEGACY_MISSING_CANONICAL_PATH
    if body["canonicalPath"] != canonical_path:
        return SnapshotValidationResult.PATH_MISMATCH
    return SnapshotValidationResult.VALID


_LEGACY_SNAPSHOT_WARNED: set[tuple[str, str]] = set()


def legacy_snapshot_migration_command(category_name: str, basename: str) -> str:
    """Return the literal shim command that migrates a legacy snapshot dir.

    Routes through :func:`command_templates.build_migrate_legacy_snapshot_command`
    so every surface that surfaces the migration step shares one
    byte-equal shape.
    """
    # Local import — command_templates does not import approvals, so a
    # module-level import would couple two unrelated APIs at startup.
    from .command_templates import build_migrate_legacy_snapshot_command
    return build_migrate_legacy_snapshot_command(
        spec=category_name, doc=basename,
    )


def _warn_legacy_snapshot_once(
    category_name: str, basename: str, canonical_path: str,
) -> None:
    """Warn at most once per ``(category, basename)`` per invocation."""
    key = (category_name, basename)
    if key in _LEGACY_SNAPSHOT_WARNED:
        return
    _LEGACY_SNAPSHOT_WARNED.add(key)
    migration_command = legacy_snapshot_migration_command(category_name, basename)
    _output_warn(
        f"Legacy snapshot at .approvals/{category_name}/.snapshots/{basename}/ "
        f"matches content hash but lacks canonicalPath. "
        f"Run `{migration_command}` to backfill canonicalPath in place "
        f"(idempotent)."
    )


def read_approval(approval_path: Path) -> dict:
    """Read and validate an approval JSON. Returns the raw dict for callers.

    Malformed records surface via ``ApprovalRecord.from_dict``: the parser
    is total — instead of raising on bad input it returns a record whose
    ``schema_state == "malformed"``. Callers expect a ``dict``, so this
    function still raises ``ValueError`` on the malformed path; legacy
    records (missing ``canonicalPath`` / ``contentHash``) read normally —
    the *gate* refuses them, not the reader.
    """
    raw = json.loads(Path(approval_path).read_text(encoding="utf-8"))
    parsed = ApprovalRecord.from_dict(raw)
    if parsed.schema_state == "malformed":
        reason = parsed.verification.reason or "schema validation failed"
        raise ValueError(
            f"Malformed approval record at {approval_path}: {reason}"
        )
    return raw


def write_approval(approval_path: Path, approval: dict) -> None:
    """Write approval JSON atomically with read-back verification."""
    atomic_write_json(str(approval_path), approval, verify_key="id")


def scan_approvals(
    approvals_root: Path,
    category: str | None = None,
    status_filter: str | None = None,
    warn_callback: Callable[[str], None] | None = None,
) -> list[dict]:
    """Scan approval JSONs, optionally filtered. Skips .snapshots/.

    When warn_callback is provided, it is called with a message string
    for each skipped file (empty, malformed, missing status).
    """
    results = []
    if not approvals_root.is_dir():
        return results
    for root_dir, dirs, files in os.walk(approvals_root):
        dirs[:] = [d for d in dirs if d != ".snapshots"]
        for filename in sorted(files):
            if not filename.endswith(".json"):
                continue
            fpath = Path(root_dir) / filename
            if fpath.stat().st_size == 0:
                if warn_callback:
                    warn_callback(f"Empty file skipped: {fpath}")
                continue
            try:
                data = json.loads(fpath.read_text())
            except (json.JSONDecodeError, OSError):
                if warn_callback:
                    warn_callback(f"JSON parse error skipped: {fpath}")
                continue
            if not data.get("status"):
                if warn_callback:
                    warn_callback(f"Missing status field skipped: {fpath}")
                continue
            parsed = ApprovalRecord.from_dict(data)
            if parsed.schema_state == "malformed":
                if warn_callback:
                    reason = (
                        parsed.verification.reason
                        or "schema validation failed"
                    )
                    warn_callback(
                        f"Malformed approval skipped ({reason}): {fpath}"
                    )
                continue
            if status_filter and data.get("status") != status_filter:
                continue
            if category and data.get("category") != category:
                continue
            data["_source_file"] = str(fpath)
            results.append(data)
    return results


def find_approval_by_id(approvals_root: Path, approval_id: str) -> tuple[Path, dict] | None:
    """Find a specific approval by ID across all categories."""
    if not approvals_root.is_dir():
        return None
    for root_dir, dirs, files in os.walk(approvals_root):
        dirs[:] = [d for d in dirs if d != ".snapshots"]
        for filename in sorted(files):
            if not filename.endswith(".json"):
                continue
            fpath = Path(root_dir) / filename
            try:
                data = json.loads(fpath.read_text())
                if data.get("id") == approval_id:
                    return (fpath, data)
            except (json.JSONDecodeError, OSError):
                continue
    return None


APPROVAL_ID_HEX_DIGITS = 8  # hex chars of randomness — ~4 billion unique IDs per second


def create_approval_id() -> str:
    """Generate approval_<timestamp>_<random> ID."""
    ts = int(datetime.now(timezone.utc).timestamp())
    rand = f"{random.randint(0, 0xFFFFFFFF):0{APPROVAL_ID_HEX_DIGITS}x}"
    return f"approval_{ts}_{rand}"


def filter_by_age(approvals: list[dict], max_age_days: int) -> tuple[list[dict], list[dict]]:
    """Split approvals into (expired, current) based on createdAt age."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max_age_days)
    expired, current = [], []
    for a in approvals:
        created = a.get("createdAt", "")
        try:
            dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            if dt < cutoff:
                expired.append(a)
            else:
                current.append(a)
        except (ValueError, TypeError):
            from .output import warn as _warn
            _warn(f"Unparseable createdAt '{created}' in approval — treating as current")
            current.append(a)
    return expired, current


def _expected_hash_token(expected_hash: str) -> str:
    """Normalise the caller-supplied hash to the ``sha256:<hex>`` form."""
    if not expected_hash:
        return ""
    if expected_hash.startswith("sha256:"):
        return expected_hash
    return f"sha256:{expected_hash}"


def _is_verifiable(record: dict) -> bool:
    """True when *record* is current, approved, and carries the new identity fields."""
    if record.get("status") != "approved":
        return False
    parsed = ApprovalRecord.from_dict(record)
    if parsed.schema_state != "current":
        return False
    return parsed.verification.state is VerificationState.CURRENT


def has_approved(
    approvals_list: list[dict],
    canonical_path: str,
    expected_hash: str,
) -> bool:
    """Match by canonical absolute path + exact ``contentHash``.

    ``expected_hash`` may be the raw hex digest or the ``sha256:<hex>``
    form. Returns ``True`` only when an approved record matches both
    the canonical path *and* the stored hash, and
    ``verification.state == "current"``. Drifted, legacy, or
    malformed records never satisfy the gate.
    """
    wanted = _expected_hash_token(expected_hash)
    for record in approvals_list:
        if not _is_verifiable(record):
            continue
        if record.get("canonicalPath") != canonical_path:
            continue
        stored = record.get("contentHash") or ""
        if stored != wanted:
            continue
        return True
    return False


def has_approved_any(
    approvals_list: list[dict],
    canonical_path: str,
    expected_hash: str,
    approvals_root: Path | None = None,
    category_name: str | None = None,
) -> bool:
    """Active-then-snapshot fallback; both layers match on identity + hash."""
    if has_approved(approvals_list, canonical_path, expected_hash):
        return True
    if approvals_root and category_name:
        return has_approved_snapshot(
            approvals_root, category_name, canonical_path, expected_hash,
        )
    return False


def has_approved_audit(
    audit_log_path: Path,
    file_path: str,
    *,
    category_name: str | None = None,
) -> bool:
    """True when ``approval-audit.log`` records an approve transition for *file_path*.

    The audit log is the immutable transition ledger emitted by
    :mod:`approval/update-status.py`; per-doc consultation lets
    ``check-status.py`` answer "did this phase ever clear?" even when
    the snapshot directory was rotated. The match is on the recorded
    ``filePath`` (singular) — single source for the doc identity since
    the audit record carries one entry per ``update-status`` call.

    ``category_name`` further constrains the match to the given target
    when supplied so a steering ``requirements.md`` (hypothetical) does
    not satisfy a spec phase. Empty / missing fields fall back to a
    plain path match.
    """
    if not audit_log_path or not file_path:
        return False
    try:
        text = Path(audit_log_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    wanted = file_path.replace("\\", "/")
    basename = wanted.rsplit("/", 1)[-1]
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(entry, dict):
            continue
        if entry.get("newStatus") != "approved":
            continue
        if category_name and entry.get("categoryName") != category_name:
            continue
        recorded = (entry.get("filePath") or "").replace("\\", "/")
        if recorded == wanted:
            return True
        if recorded and recorded.rsplit("/", 1)[-1] == basename:
            return True
    return False


def has_approved_snapshot(
    approvals_root: Path,
    category_name: str,
    canonical_path: str,
    expected_hash: str,
) -> bool:
    """True when a snapshot matches the canonical-path identity and content hash."""
    wanted = _expected_hash_token(expected_hash)
    basename = Path(canonical_path).name
    snap_dir = approvals_root / category_name / ".snapshots" / basename
    meta_path = snap_dir / "metadata.json"
    if not meta_path.is_file():
        return False
    try:
        meta = json.loads(meta_path.read_text())
    except (json.JSONDecodeError, OSError):
        return False
    for snap in reversed(meta.get("snapshots", [])):
        if snap.get("trigger") != "approved":
            continue
        snap_file_name = snap.get("snapshotFile")
        if not snap_file_name:
            continue
        snap_file = snap_dir / snap_file_name
        if not snap_file.is_file():
            continue
        try:
            body = json.loads(snap_file.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        result = validate_approval_snapshot(body, canonical_path, wanted)
        if result is SnapshotValidationResult.VALID:
            return True
        if result is SnapshotValidationResult.LEGACY_MISSING_CANONICAL_PATH:
            _warn_legacy_snapshot_once(category_name, basename, canonical_path)
    return False
