"""Append-only ledger of mandatory pre-flight reads/runs per spec.

Every precondition script that represents a MUST-READ or MUST-RUN for a
spec (`util/detect-doc-state.py`, etc.) appends one JSON line on success
so that ``pipeline_phases/launch_preconditions.py`` can verify the
required calls were made before ``--phase launch`` advances the gate.

The ledger lives at
``{project_path}/.spec-workflow/<bucket>/<target>/.sdd-state/reference-ledger.jsonl``
where *bucket* is one of ``specs`` / ``steering`` / ``discovery`` /
``workspace`` (mapped from the audit ``category`` via
``sdd_core.paths._CATEGORY_BUCKETS``). ``.sdd-state/`` is the sole
contract; any other on-disk artefact is ignored. The audit *channel*
is metadata only — it never contributes a path component.

Design notes:
  * Append-only (no removal / rewrite APIs).
  * Rotates at 1 MiB — the stale half is renamed to ``reference-ledger.jsonl.1``.
  * Idempotent callers — duplicates are permitted; lookup helpers use the
    most recent entry keyed on ``(script, doc)``.
  * No session-state coupling; the module only reads/writes its own file
    so ``review_quality/gate_session`` imports it safely.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from sdd_core import transient_state
from sdd_core.time import ts_compact, ts_now

__all__ = [
    "LedgerEntry",
    "ledger_path",
    "append",
    "append_read",
    "reference_read_script_id",
    "read_entries",
    "latest_by",
    "hash_file",
    "verify_and_record_read",
    "archive_to",
    "LEDGER_FILENAME",
    "MAX_BYTES",
    "READ_SCRIPT_PREFIX",
]

# Canonical basename (inside ``.sdd-state/``).
LEDGER_FILENAME = transient_state.LEDGER_FILENAME
# Rotation threshold: 1 MiB keeps a single ledger file trivially
# grep-able on disk while covering dozens of launch cycles; crossing
# it renames the stale half to ``reference-ledger.jsonl.1``.
MAX_BYTES = 1_048_576
# Script identifiers for read-receipt ledger entries use this prefix so
# ``launch_preconditions`` can distinguish them from script-run entries
# without another schema field.
READ_SCRIPT_PREFIX = "read/"


@dataclass(frozen=True)
class LedgerEntry:
    """A single ledger line (decoded from JSON)."""

    ts: str
    script: str
    category: str
    target_name: str
    doc: str | None = None
    sha256: str | None = None
    extra: dict | None = None

    def to_dict(self) -> dict:
        payload = {
            "ts": self.ts,
            "script": self.script,
            "category": self.category,
            "target_name": self.target_name,
        }
        if self.doc is not None:
            payload["doc"] = self.doc
        if self.sha256 is not None:
            payload["sha256"] = self.sha256
        if self.extra:
            payload["extra"] = self.extra
        return payload


def ledger_path(category: str, target_name: str, project_path: str = "") -> str:
    """Return the canonical ledger path under ``.sdd-state/``."""
    return transient_state.state_path(
        category, target_name, LEDGER_FILENAME, project_path,
    )


def _rotate_if_needed(path: str) -> None:
    try:
        size = os.path.getsize(path)
    except OSError:
        return
    if size < MAX_BYTES:
        return
    rotated = path + ".1"
    try:
        if os.path.exists(rotated):
            os.remove(rotated)
        os.replace(path, rotated)
    except OSError:
        # Best effort — a failed rotation must not block the append.
        pass


def append(
    *,
    category: str,
    target_name: str,
    script: str,
    doc: str | None = None,
    sha256: str | None = None,
    project_path: str = "",
    extra: dict | None = None,
) -> LedgerEntry:
    """Append one entry. Silently no-ops if the ledger dir cannot be created.

    ``script`` MUST use the ``group/name.py`` form so
    ``launch_preconditions`` can match on the stable identifier (e.g.
    ``"util/detect-doc-state.py"``).
    """
    entry = LedgerEntry(
        ts=ts_now(),
        script=script,
        category=category,
        target_name=target_name,
        doc=doc,
        sha256=sha256,
        extra=extra or None,
    )
    # Pipeline dry-run (redesign § C4 / S13): compute the entry so the
    # caller's return value is unchanged, but skip every disk touch
    # that would leak state out of the dry-run subprocess. Callers that
    # use the ``LedgerEntry`` for in-process chaining (e.g. to build a
    # verification response) still see it; the ``.jsonl`` file stays
    # untouched.
    from sdd_core.output import _dry_run_active  # local: avoid cycle
    if _dry_run_active():
        return entry
    path = ledger_path(category, target_name, project_path)
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return entry

    line = json.dumps(entry.to_dict(), separators=(",", ":"), sort_keys=True)
    try:
        from sdd_core.security.state import TransactionalStore
        with TransactionalStore(path) as store:
            # Re-check rotation under the lock — another writer could
            # have rotated between any pre-lock size check and the
            # append, so the decision lives inside the critical section.
            _rotate_if_needed(path)
            store.append_line(line)
    except OSError:
        # Ledger writes are advisory — never crash the calling script.
        pass
    return entry


def read_entries(
    category: str, target_name: str, project_path: str = "",
) -> list[LedgerEntry]:
    """Return every entry in chronological order. Absent file → empty list.

    Reads only the canonical ``.sdd-state/`` path; a missing file
    yields an empty list so a fresh workspace silently starts a new
    ledger.
    """
    path = ledger_path(category, target_name, project_path)
    if not os.path.exists(path):
        return []
    entries: list[LedgerEntry] = []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    obj = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                entries.append(
                    LedgerEntry(
                        ts=obj.get("ts", ""),
                        script=obj.get("script", ""),
                        category=obj.get("category", ""),
                        target_name=obj.get("target_name", ""),
                        doc=obj.get("doc"),
                        sha256=obj.get("sha256"),
                        extra=obj.get("extra"),
                    )
                )
    except OSError:
        return []
    return entries


def latest_by(
    entries: Iterable[LedgerEntry],
    *,
    script: str,
    doc: str | None = None,
) -> LedgerEntry | None:
    """Return the most recent entry matching ``script`` (and ``doc`` if set)."""
    match: LedgerEntry | None = None
    for entry in entries:
        if entry.script != script:
            continue
        if doc is not None and entry.doc != doc:
            continue
        match = entry
    return match


def hash_file(
    path: "str | Path",
    *,
    limit_hex_chars: "int | None" = None,
    missing_sentinel: str = "",
) -> str:
    """SHA-256 of a file's bytes.

    ``limit_hex_chars`` truncates the hex digest (use 16 for short cache
    keys; leave ``None`` for the full 64-char digest on ledger entries).
    ``missing_sentinel`` is returned when the file cannot be read — the
    ledger uses the empty string; gate-session cache keys use
    ``"<missing>"`` so that absent artifacts still participate in the
    key function.
    """
    try:
        with open(path, "rb") as fh:
            digest = hashlib.sha256(fh.read()).hexdigest()
    except OSError:
        return missing_sentinel
    if limit_hex_chars is not None:
        return digest[:limit_hex_chars]
    return digest


def reference_read_script_id(reference_path: str | Path) -> str:
    """Canonicalise a reference path into a ledger ``script`` identifier.

    The returned identifier uses the ``read/`` prefix plus an absolute
    path so ``launch_preconditions`` can match literal paths without
    worrying about relative-vs-absolute or symlink differences. Callers
    should pass already-resolved absolute paths; the helper calls
    ``os.path.abspath`` defensively so a relative path still produces a
    stable identifier.
    """
    normalised = os.path.abspath(os.fspath(reference_path))
    return f"{READ_SCRIPT_PREFIX}{normalised}"


def verify_and_record_read(
    *,
    name: str,
    expected_sha256: str,
    echoed_sha256: str,
    category: str,
    target_name: str,
    reference_path: str | Path,
    project_path: str = "",
) -> tuple[bool, "str | None"]:
    """Verify ``echoed_sha256`` matches ``expected_sha256`` and append a read.

    Returns ``(True, None)`` when the hashes agree and the ledger was
    appended; ``(False, "<reason>")`` otherwise. Callers dispatch on the
    bool instead of reimplementing the "hash compare → ledger append"
    sequence — single authority for reference-read verification.

    ``name`` is carried into the ledger ``extra`` bag so auditors can
    trace the verified precondition back to the launch envelope.
    """
    if not echoed_sha256:
        return False, "missing echoed sha256"
    if not expected_sha256:
        return False, "missing expected sha256 (reference unreadable?)"
    if echoed_sha256 != expected_sha256:
        return False, (
            f"sha256 mismatch for {name!r}: "
            f"expected {expected_sha256}, got {echoed_sha256}"
        )
    append_read(
        category=category,
        target_name=target_name,
        reference_path=reference_path,
        project_path=project_path,
        sha256=echoed_sha256,
        extra={"name": name, "verified_by": "verify_and_record_read"},
    )
    return True, None


def append_read(
    *,
    category: str,
    target_name: str,
    reference_path: str | Path,
    project_path: str = "",
    sha256: str | None = None,
    extra: dict | None = None,
) -> LedgerEntry:
    """Record a read-receipt entry for a reference file.

    Thin wrapper over :func:`append` that normalises the identifier via
    :func:`reference_read_script_id`. Every call is a successful read;
    ``launch_preconditions`` only consumes the presence of the entry.
    """
    script = reference_read_script_id(reference_path)
    file_sha: str | None = sha256
    if file_sha is None:
        computed = hash_file(reference_path)
        file_sha = computed or None
    return append(
        category=category,
        target_name=target_name,
        script=script,
        doc=None,
        sha256=file_sha,
        project_path=project_path,
        extra=extra,
    )


def archive_to(
    category: str,
    target_name: str,
    *,
    project_path: str = "",
    timestamp: str | None = None,
) -> str | None:
    """Move the current ledger into ``.sdd-state/.archive/`` and return
    the archived path. Returns ``None`` when no ledger exists.

    Used by the approval-completion cleanup facade (see
    ``sdd_core.transient_state.cleanup_on_approval``). The ledger is an
    audit trail, so we ``os.replace`` it under ``.archive/`` rather
    than deleting it outright.

    Honours the pipeline dry-run flag — inside a dry run this is a no-op
    and returns ``None`` so subprocesses never leak state.
    """
    from sdd_core.output import _dry_run_active
    if _dry_run_active():
        return None

    src = ledger_path(category, target_name, project_path)
    if not os.path.exists(src):
        return None

    state_root = transient_state.state_dir(category, target_name, project_path)
    archive_dir = os.path.join(state_root, ".archive")
    try:
        Path(archive_dir).mkdir(parents=True, exist_ok=True)
    except OSError:
        return None

    stamp = timestamp or ts_compact()
    dest = os.path.join(archive_dir, f"ledger-{stamp}.jsonl")
    # Guard against collisions (same second → overwrite would break the
    # audit guarantee). Append a short counter if needed.
    counter = 1
    while os.path.exists(dest):
        dest = os.path.join(archive_dir, f"ledger-{stamp}-{counter}.jsonl")
        counter += 1

    try:
        os.replace(src, dest)
    except OSError:
        return None
    return dest
