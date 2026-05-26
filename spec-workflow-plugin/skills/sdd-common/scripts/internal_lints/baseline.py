"""Set-membership baseline helpers for lint ratchets.

Baselines for every rule live in a single ``baselines.json`` manifest
keyed by rule id. Each rule's ``entries`` is a sorted list of
``{file, line, reason}`` triples. The canonical *internal* key format
remains ``<rel_path>::<line>::<reason>`` so consumer code (lint
checkers, ``key_for``, ``diff_baseline``) is unchanged; only the
on-disk representation moves to JSON.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable, Sequence

from sdd_core.security.state import atomic_write_text

from . import LintFinding
from .constants import (
    BASELINE_DEFAULT_REASON,
    BASELINE_KEY_SEPARATOR,
    BASELINE_MANIFEST_FILENAME,
    BASELINE_SCHEMA_VERSION,
)

__all__ = [
    "read_baseline",
    "write_baseline",
    "key_for",
    "diff_baseline",
    "MANIFEST_PATH",
    "SCHEMA_VERSION",
    "parse_key",
]


MANIFEST_PATH = Path(__file__).with_name(BASELINE_MANIFEST_FILENAME)
SCHEMA_VERSION = BASELINE_SCHEMA_VERSION


def _resolve_repo_rel(path: str) -> str:
    """Render *path* relative to the workspace root when possible."""
    abs_path = os.path.abspath(path)
    cur = Path(abs_path).parent
    while cur != cur.parent:
        if (cur / ".cursor" / "skills").is_dir() or (cur / ".claude" / "skills").is_dir():
            try:
                return str(Path(abs_path).relative_to(cur))
            except ValueError:
                break
        cur = cur.parent
    return abs_path


def key_for(finding: LintFinding) -> str:
    rel = _resolve_repo_rel(finding.file)
    reason = (finding.extra or {}).get("reason") or BASELINE_DEFAULT_REASON
    return BASELINE_KEY_SEPARATOR.join((rel, str(finding.line), reason))


def parse_key(key: str) -> dict:
    """Split ``<file>::<line>::<reason>`` back into structured fields."""
    parts = key.split(BASELINE_KEY_SEPARATOR, 2)
    if len(parts) < 3:
        return {"file": key, "line": 0, "reason": BASELINE_DEFAULT_REASON}
    file_, line_str, reason = parts
    try:
        line = int(line_str)
    except ValueError:
        line = 0
    return {"file": file_, "line": line, "reason": reason}


def _load_manifest(manifest_path: Path) -> dict:
    if not manifest_path.is_file():
        return {"schemaVersion": SCHEMA_VERSION, "rules": {}}
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schemaVersion": SCHEMA_VERSION, "rules": {}}


def read_baseline(
    rule_id: str, *, manifest_path: "Path | None" = None,
) -> set[str]:
    """Return the set of canonical keys for *rule_id*."""
    target = manifest_path or MANIFEST_PATH
    manifest = _load_manifest(target)
    rule = manifest.get("rules", {}).get(rule_id) or {}
    keys: set[str] = set()
    for entry in rule.get("entries", []):
        f = entry.get("file", "")
        line = entry.get("line", 0)
        reason = entry.get("reason", BASELINE_DEFAULT_REASON) or BASELINE_DEFAULT_REASON
        keys.add(BASELINE_KEY_SEPARATOR.join((f, str(line), reason)))
    return keys


def write_baseline(
    rule_id: str,
    entries: Iterable[str],
    *,
    manifest_path: "Path | None" = None,
) -> None:
    """Replace *rule_id*'s entries; other rules pass through untouched.

    Entries are sorted on write by ``(file, line, reason)`` for diff-
    friendliness. The whole manifest is atomic-replaced via
    :func:`sdd_core.security.state.atomic_write_text`.
    """
    target = manifest_path or MANIFEST_PATH
    manifest = _load_manifest(target)
    manifest.setdefault("schemaVersion", SCHEMA_VERSION)
    rules = manifest.setdefault("rules", {})

    structured: list[dict] = []
    for key in sorted(set(entries)):
        structured.append(parse_key(key))
    structured.sort(key=lambda e: (e["file"], e["line"], e["reason"]))

    rules.setdefault(rule_id, {})["entries"] = structured
    payload = json.dumps(manifest, indent=2, sort_keys=False) + "\n"
    atomic_write_text(target, payload)


def diff_baseline(
    observed: Sequence[str],
    baseline: "Iterable[str] | None" = None,
    *,
    rule_id: "str | None" = None,
    manifest_path: "Path | None" = None,
) -> dict[str, list[str]]:
    """Return ``{"new": [...], "stale": [...], "known": [...]}``.

    Provide either an iterable *baseline* directly or a *rule_id* (which
    looks the entries up via :func:`read_baseline`). Sorted output.
    """
    if baseline is None:
        baseline_set = (
            read_baseline(rule_id, manifest_path=manifest_path)
            if rule_id else set()
        )
    else:
        baseline_set = set(baseline)
    observed_set = set(observed)
    return {
        "new": sorted(observed_set - baseline_set),
        "stale": sorted(baseline_set - observed_set),
        "known": sorted(observed_set & baseline_set),
    }
