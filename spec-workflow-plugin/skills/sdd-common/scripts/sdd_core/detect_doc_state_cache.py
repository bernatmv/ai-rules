"""Content-hash cache for ``util/detect-doc-state.py`` results.

The detection output is deterministic in the set of doc contents — if
every target doc's SHA-256 is unchanged, the previously-computed
envelope is still authoritative. Caching here turns re-entries of the
same gate into a <50 ms lookup instead of a full filesystem walk.

Cache files live under the workflow-level state tree:
``<workflow-root>/.spec-workflow/.sdd-state/detect-doc-state/<category>/
<target-name>/<sha>.json``. Co-locating the cache inside the target
doc directory would make directory probes (``discovery/init-project.py``,
``spec/...``) misread a cache side-effect as project ownership.

Contract:

* :func:`compute_state_sha` returns the content hash for a set of
  target doc paths. Missing files contribute a stable ``<missing>``
  token so the cache key remains deterministic when a doc is deleted.
* :func:`load_cached` returns the cached payload or ``None`` on miss.
* :func:`store` writes the payload (best-effort; unwritable state
  dirs silently no-op, mirroring :mod:`transient_state`).
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Iterable

from sdd_core.paths import detect_doc_state_cache_dir
from sdd_core.reference_ledger import hash_file

__all__ = [
    "CACHE_SUBDIR",
    "compute_state_sha",
    "cache_path",
    "load_cached",
    "store",
]


CACHE_SUBDIR = "detect-doc-state"
_MISSING_TOKEN = "<missing>"


def compute_state_sha(paths: Iterable[str]) -> str:
    """Return a deterministic content hash across *paths*.

    Paths are processed in sorted order so the key is stable regardless
    of caller ordering. Missing files contribute the
    :data:`_MISSING_TOKEN` token so the cache still refreshes when a
    target doc appears / disappears.
    """
    hasher = hashlib.sha256()
    for p in sorted(paths):
        hasher.update(p.encode("utf-8"))
        hasher.update(b"\0")
        file_hash = hash_file(p) if os.path.isfile(p) else _MISSING_TOKEN
        hasher.update(file_hash.encode("utf-8"))
        hasher.update(b"\0")
    return hasher.hexdigest()


def _ensure_cache_dir(root: str, category: str, target_name: str) -> Path:
    cache_dir = detect_doc_state_cache_dir(root, category, target_name)
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return cache_dir


def cache_path(
    root: str, category: str, target_name: str, state_sha: str,
) -> str:
    """Return the cache-file path for *(category, target_name, sha)*."""
    return str(
        detect_doc_state_cache_dir(root, category, target_name)
        / f"{state_sha}.json"
    )


def load_cached(
    root: str, category: str, target_name: str, state_sha: str,
) -> dict | None:
    """Return the cached payload for *state_sha*, or ``None`` on miss."""
    path = cache_path(root, category, target_name, state_sha)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def store(
    root: str,
    category: str,
    target_name: str,
    state_sha: str,
    payload: dict,
) -> None:
    """Write *payload* to the cache; silent on permission errors."""
    cache_dir = _ensure_cache_dir(root, category, target_name)
    path = cache_dir / f"{state_sha}.json"
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, separators=(",", ":"), sort_keys=True)
    except OSError:
        pass
