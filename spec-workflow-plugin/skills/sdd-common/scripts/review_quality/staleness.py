"""Canonical staleness check for review artifacts.

Single source of truth for determining whether a document has been modified
since its last review. Used by both prepare-pipeline.py and check-re-review.py.

The :func:`is_review_artifact_stale` entry point collapses three
ad-hoc staleness checks (``check_reval``, ``pre_approval``,
``workspace_health_checks``) onto one primitive. Callers pick a *kind*
hint (``content_hash`` or ``timestamp``); the underlying answer is
consistent across them.
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Literal

from sdd_core import output
from sdd_core.time import ts_from_epoch


DOC_KEY_SUFFIX: str = "_md"
"""Suffix appended to spec-doc keys in review-quality.json (``tasks_md``,
``requirements_md``). Single owner so emit sites do not restate the
literal; ``doc_key`` and ``doc_stem`` route through this constant.
"""


def doc_key(doc_filename: str) -> str:
    """Convert filename to review-quality.json document key: 'tasks.md' -> 'tasks_md'."""
    return doc_filename.replace(".", "_").replace("-", "_")


def doc_stem(doc_filename: str) -> str:
    """Convert filename to stem for cross-validation pair matching: 'ui-design.md' -> 'ui_design'."""
    return doc_key(doc_filename).removesuffix(DOC_KEY_SUFFIX)


def _get_mtime_dt(path: str) -> datetime:
    """Return the document's mtime as a timezone-aware UTC datetime."""
    return datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc)


def doc_mtime_iso(doc_path: str) -> str:
    """Return the document's mtime as a UTC ISO-8601 string.

    Raises:
        OSError: If *doc_path* does not exist or is not accessible.
    """
    return ts_from_epoch(os.path.getmtime(doc_path))


def check_docs_staleness(
    doc_list: list[str], doc_directory: str, quality_data: dict,
) -> tuple[list[str], list[str]]:
    """Batch staleness check. Returns (stale_docs, fresh_docs)."""
    stale, fresh = [], []
    for doc in doc_list:
        doc_path = os.path.join(doc_directory, doc)
        if not os.path.isfile(doc_path):
            continue
        if is_doc_stale(doc_path, quality_data, doc):
            stale.append(doc)
        else:
            fresh.append(doc)
    return stale, fresh


def get_doc_entry(quality_data: dict, doc_filename: str) -> dict | None:
    """Unified access for doc entries across artifact shapes."""
    dk = doc_key(doc_filename)
    docs = quality_data.get("documents")
    if isinstance(docs, dict) and dk in docs:
        return docs[dk]
    if dk in quality_data:
        return quality_data[dk]
    return None


def set_doc_field(quality_data: dict, doc_filename: str, field: str, value) -> None:
    """Unified setter for doc entry fields across artifact shapes."""
    dk = doc_key(doc_filename)
    docs = quality_data.get("documents")
    if isinstance(docs, dict) and dk in docs:
        docs[dk][field] = value
    elif dk in quality_data:
        quality_data[dk][field] = value


def is_doc_stale(doc_path: str, quality_data: dict, doc_filename: str) -> bool:
    """Return True if the doc was modified after its last review timestamp.

    Resolution order:
      1. Per-document ``documents[key].last_reviewed_at`` (most precise)
      2. Artifact-level ``generated_at`` (fallback for legacy artifacts)

    Raises:
        OSError: If *doc_path* does not exist or is not accessible.
    """
    dk = doc_key(doc_filename)
    doc_entry = (quality_data.get("documents") or {}).get(dk)

    review_timestamp = None
    if doc_entry is not None:
        review_timestamp = doc_entry.get("last_reviewed_at")
    if not review_timestamp:
        review_timestamp = quality_data.get("generated_at", "")
    if not review_timestamp:
        return False

    doc_modified_dt = _get_mtime_dt(doc_path)
    try:
        review_dt = datetime.fromisoformat(review_timestamp.replace("Z", "+00:00"))
    except ValueError:
        output.warn(
            f"Unparseable review timestamp {review_timestamp!r} for {doc_filename} — treating as stale"
        )
        return True
    return doc_modified_dt > review_dt


# Canonical content-hash + staleness primitive
# ---------------------------------------------
#
# ``compute_doc_hash`` and ``compute_document_hashes`` produce the
# ``document_hashes`` block that ``update-quality.py`` records into the
# review-quality artifact. ``is_review_artifact_stale`` is the single
# entry point every caller (``check_reval``, ``pre_approval``,
# ``workspace_health_checks``) now consults — it answers "is this
# review-quality artifact out of sync with the docs?" with either
# content-hash or mtime semantics.

# 64 KiB — page-cache aligned and matches Python's _io.DEFAULT_BUFFER_SIZE.
_HASH_CHUNK = 65536


def compute_doc_hash(doc_path: str | Path) -> str:
    """Return the SHA-256 hex digest of *doc_path*'s bytes.

    Streamed read so large docs don't blow memory. Returns empty
    string on OSError so callers can record a "not hashable" entry
    without raising.
    """
    h = hashlib.sha256()
    try:
        with open(doc_path, "rb") as fh:
            for chunk in iter(lambda: fh.read(_HASH_CHUNK), b""):
                h.update(chunk)
    except OSError:
        return ""
    return h.hexdigest()


def compute_document_hashes(
    doc_dir: str | Path,
    doc_filenames: Iterable[str],
) -> dict[str, str]:
    """Return ``{filename: sha256_hex}`` for each readable doc.

    Files that don't exist or aren't readable are skipped silently —
    the artifact only records hashes for docs that actually exist on
    disk at write time, so a future caller comparing live bytes never
    sees a stale-by-default phantom.
    """
    out: dict[str, str] = {}
    base = Path(doc_dir)
    for filename in doc_filenames:
        path = base / filename
        if not path.is_file():
            continue
        digest = compute_doc_hash(path)
        if digest:
            out[filename] = digest
    return out


@dataclass(frozen=True)
class StalenessResult:
    """Single answer shape for :func:`is_review_artifact_stale`.

    *drifted* is the bottom-line boolean every caller checks. *drifted_docs*
    enumerates the filenames that diverged so callers can surface a
    targeted advisory ("requirements.md drifted — re-review needed")
    rather than a blanket "spec is stale" headline.

    *kind* echoes the mode that produced the answer
    (``content_hash`` / ``timestamp``); ``unverifiable`` is the third
    state — neither hashes nor timestamps were available, so the caller
    treats the artifact as fresh by default.
    """

    drifted: bool
    drifted_docs: tuple[str, ...] = ()
    kind: Literal["content_hash", "timestamp", "unverifiable"] = "unverifiable"
    detail: str = ""


def is_review_artifact_stale(
    artifact: dict,
    doc_dir: str | Path,
    doc_filenames: Iterable[str],
    *,
    kind: Literal["content_hash", "timestamp"] = "content_hash",
) -> StalenessResult:
    """Single answer to "is the recorded review out of sync with the docs?".

    ``kind="content_hash"`` (default): compares each doc's live
    ``sha256`` against the recorded ``document_hashes`` block.
    Tolerant of mtime jitter, deterministic. Falls back to
    ``timestamp`` for artifacts predating the hash backfill (no
    ``document_hashes`` recorded) — same behaviour as before, no
    regression.

    ``kind="timestamp"`` (legacy): compares each doc's mtime against
    its ``last_reviewed_at`` (or the artifact-level ``generated_at``).
    """
    filenames = tuple(doc_filenames)

    if kind == "content_hash":
        recorded_hashes = artifact.get("document_hashes") or {}
        if isinstance(recorded_hashes, dict) and recorded_hashes:
            return _compare_hashes(recorded_hashes, doc_dir, filenames)
        # Legacy artifact: fall back to timestamp comparison.

    drifted_docs: list[str] = []
    base = Path(doc_dir)
    for filename in filenames:
        path = base / filename
        if not path.is_file():
            continue
        try:
            if is_doc_stale(str(path), artifact, filename):
                drifted_docs.append(filename)
        except OSError:
            continue
    return StalenessResult(
        drifted=bool(drifted_docs),
        drifted_docs=tuple(drifted_docs),
        kind="timestamp",
        detail=("docs newer than last_reviewed_at" if drifted_docs else ""),
    )


def _compare_hashes(
    recorded: dict,
    doc_dir: str | Path,
    filenames: tuple[str, ...],
) -> StalenessResult:
    """Hash-comparison branch of :func:`is_review_artifact_stale`."""
    base = Path(doc_dir)
    drifted_docs: list[str] = []
    for filename in filenames:
        path = base / filename
        if not path.is_file():
            continue
        recorded_hash = recorded.get(filename)
        if not isinstance(recorded_hash, str) or not recorded_hash:
            continue
        live_hash = compute_doc_hash(path)
        if not live_hash:
            continue
        if live_hash != recorded_hash:
            drifted_docs.append(filename)
    return StalenessResult(
        drifted=bool(drifted_docs),
        drifted_docs=tuple(drifted_docs),
        kind="content_hash",
        detail=(
            f"sha256 drift: {', '.join(drifted_docs)}" if drifted_docs else ""
        ),
    )


