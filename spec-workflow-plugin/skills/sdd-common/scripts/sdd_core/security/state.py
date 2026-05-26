"""Locked, fsync-durable read-modify-write primitive for state files.

POSIX-only (``fcntl.flock``) — consistent with the plugin's platform
contract. Every public entry point honours
``sdd_core.output._dry_run_active()``; when dry-run is active the
module never opens a lockfile, never creates a temp file, and never
calls ``os.replace`` — the same gate ``output.atomic_write_json``,
``reference_ledger.append``, and ``reference_acks.record_ack`` already
observe.
"""
from __future__ import annotations

import contextlib
import fcntl
import json
import os
import tempfile
from pathlib import Path
from typing import Any

__all__ = [
    "TransactionalStore",
    "atomic_write_text",
    "atomic_backup_then_replace",
]


def atomic_write_text(target: "str | os.PathLike[str]", text: str) -> None:
    """Durably write *text* to *target* with orphan-tempfile cleanup.

    No-op when :func:`sdd_core.output._dry_run_active` is true — matches
    the existing ``atomic_write_json`` contract so
    ``pipeline-tick.py --dry-run`` is side-effect-free across every
    call site.

    Durability:
      * Unique per-write temp file via :class:`tempfile.NamedTemporaryFile`
        (eliminates the deterministic ``path + ".tmp"`` collision hazard).
      * ``f.flush()`` + ``os.fsync(fd)`` before ``os.replace``.
      * ``os.fsync`` on the parent directory after replace so the rename
        itself is durable.
      * Orphan tempfile cleanup in ``finally``.
    """
    from sdd_core.output import _dry_run_active  # lazy: avoid cycle
    if _dry_run_active():
        return
    target_path = Path(os.fspath(target))
    target_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=str(target_path.parent),
            prefix=f".{target_path.name}.",
            suffix=".tmp",
            delete=False,
            encoding="utf-8",
        ) as tmp:
            tmp_path = Path(tmp.name)
            tmp.write(text)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_path, target_path)
        tmp_path = None  # replaced — no longer an orphan risk
        dir_fd = os.open(str(target_path.parent), os.O_DIRECTORY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        if tmp_path is not None and tmp_path.exists():
            with contextlib.suppress(OSError):
                tmp_path.unlink()


def atomic_backup_then_replace(
    target: "str | os.PathLike[str]",
    replacement: "str | bytes",
    *,
    backup_root: "str | os.PathLike[str] | None" = None,
) -> Path:
    """Copy *target* under *backup_root* with an ISO-8601 suffix, then replace.

    Returns the backup file path so callers can surface it to the
    operator. Honours ``_dry_run_active``. ``replacement`` may be a
    ``str`` (written via :func:`atomic_write_text`) or ``bytes`` (written
    durably via a tempfile + ``os.replace``). Idempotent on retry: if
    *target* does not exist no backup is taken; the replacement still
    lands.

    When *backup_root* is omitted, the helper computes the canonical
    layout from :data:`sdd_core.constants.BACKUP_ROOT_DIR` and
    :data:`sdd_core.constants.BACKUP_TIMESTAMP_FORMAT`, rooted at the
    target's parent directory:
    ``<target.parent>/<BACKUP_ROOT_DIR>/templates-<utc-iso>/``.
    """
    from sdd_core.output import _dry_run_active  # lazy: avoid cycle

    target_path = Path(os.fspath(target))
    if backup_root is None:
        from datetime import datetime, timezone

        from sdd_core.constants import (
            BACKUP_ROOT_DIR,
            BACKUP_TIMESTAMP_FORMAT,
        )

        ts = datetime.now(timezone.utc).strftime(BACKUP_TIMESTAMP_FORMAT)
        backup_dir = (
            target_path.parent / BACKUP_ROOT_DIR / f"templates-{ts}"
        )
    else:
        backup_dir = Path(os.fspath(backup_root))

    if _dry_run_active():
        return backup_dir / target_path.name

    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / target_path.name
    if target_path.exists():
        backup_path.write_bytes(target_path.read_bytes())

    if isinstance(replacement, bytes):
        tmp_path: Path | None = None
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=str(target_path.parent),
                prefix=f".{target_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as tmp:
                tmp_path = Path(tmp.name)
                tmp.write(replacement)
                tmp.flush()
                os.fsync(tmp.fileno())
            os.replace(tmp_path, target_path)
            tmp_path = None
        finally:
            if tmp_path is not None and tmp_path.exists():
                with contextlib.suppress(OSError):
                    tmp_path.unlink()
    else:
        atomic_write_text(target_path, replacement)

    return backup_path


class TransactionalStore:
    """Exclusive-locked, fsync-durable read-modify-write over a single path.

    Lock semantics: a sidecar file ``<path>.lock`` is opened in ``a+``
    and ``fcntl.flock``-guarded with ``LOCK_EX``. The canonical target
    file itself is **never** held open across the whole context. All
    writes go through :func:`atomic_write_text`; all appends go through
    :meth:`append_line`.

    Dry-run contract: under ``SDD_PIPELINE_DRY_RUN`` the context is a
    no-op. ``__enter__`` does not open the lockfile (creating it *is*
    a disk mutation); reads still proceed normally; writes
    short-circuit.
    """

    def __init__(self, path: "str | os.PathLike[str]"):
        self.path = Path(os.fspath(path))
        self.lock_path = self.path.with_name(self.path.name + ".lock")
        self._lock_fh = None  # set only after open() succeeds
        self._dry_run = False

    def __enter__(self) -> "TransactionalStore":
        from sdd_core.output import _dry_run_active
        if _dry_run_active():
            self._dry_run = True
            return self
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(self.lock_path, "a+")
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        except OSError:
            fh.close()
            raise
        self._lock_fh = fh
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        fh = self._lock_fh
        if fh is None:
            return False
        self._lock_fh = None
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        finally:
            with contextlib.suppress(OSError):
                fh.close()
        return False  # never suppress

    # ---- read ------------------------------------------------------

    def read_json(self, default: Any = None) -> Any:
        try:
            text = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return default
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in {self.path}: {exc}") from exc

    def read_bytes(self, default: "bytes | None" = None) -> "bytes | None":
        try:
            return self.path.read_bytes()
        except FileNotFoundError:
            return default

    # ---- write -----------------------------------------------------

    def write_json(self, content: dict, *, verify_key: "str | None" = None) -> None:
        if self._dry_run:
            return
        from sdd_core.output import _verify_json_key  # lazy: avoid cycle
        atomic_write_text(self.path, json.dumps(content, indent=2) + "\n")
        if verify_key is not None:
            _verify_json_key(str(self.path), verify_key, content.get(verify_key))

    def append_line(self, line: str) -> None:
        """Durable single-line append under the lock."""
        if self._dry_run:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
            fh.flush()
            os.fsync(fh.fileno())
