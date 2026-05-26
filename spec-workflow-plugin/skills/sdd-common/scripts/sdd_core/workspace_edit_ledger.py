"""Read-only cross-repo edit ledger view over per-repo gate sessions."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable, TypedDict

from review_quality.constants import REVIEW_QUALITY_FILENAME
from review_quality.gate_session import (
    GATE_FIX_CYCLE,
    GATE_REENTRY_COUNT,
    GATE_REVIEW_GATE,
    read_session,
)
from review_quality.staleness import doc_key, is_doc_stale
from .paths import doc_dir_path

__all__ = [
    "RepoSetEntry",
    "RepoLedgerEntry",
    "build_edit_ledger",
    "stale_repos",
    "is_any_repo_stale",
]


class RepoSetEntry(TypedDict, total=False):
    """Canonical repo-set entry shape consumed by the edit ledger.

    ``repo_id`` and ``project_path`` are required; ``target_name`` is
    optional (a missing target makes the inner ledger view empty).
    Camel-case aliases (``repoId``/``repoPath``/``subSpecName``) are
    rejected at the boundary by ``build_edit_ledger`` — the workspace
    state loader is the sole place that translates between manifest /
    tracker dialects.
    """

    repo_id: str
    project_path: str
    target_name: str


class RepoLedgerEntry(TypedDict):
    last_reviewed_at: "str | None"
    last_modified_at: float
    fix_cycle: int
    reentry_count: int
    stale: bool


_REJECTED_ALIASES: dict[str, str] = {
    "repoId": "repo_id",
    "repoPath": "project_path",
    "subSpecName": "target_name",
}


def _validate_repo_entry(entry: dict) -> None:
    aliases = sorted(k for k in entry if k in _REJECTED_ALIASES)
    if aliases:
        canonical = ", ".join(f"{a}->{_REJECTED_ALIASES[a]}" for a in aliases)
        raise KeyError(
            f"workspace_edit_ledger rejects camelCase aliases ({canonical}); "
            "supply the canonical snake_case keys"
        )


def _quality_data_for(
    category: str, target_name: str, project_path: str,
) -> dict:
    q_path = Path(doc_dir_path(category, target_name, project_path)) / REVIEW_QUALITY_FILENAME
    if not q_path.is_file():
        return {}
    try:
        return json.loads(q_path.read_text(encoding="utf-8")) or {}
    except (OSError, ValueError):
        return {}


def build_edit_ledger(
    repo_set: Iterable[RepoSetEntry],
    *,
    category: str,
    docs: Iterable[str] = (),
) -> dict[str, dict[str, RepoLedgerEntry]]:
    """Walk each repo in *repo_set* and emit a read-only ledger view.

    Camel-case aliases raise ``KeyError`` so dialect drift fails fast
    at the boundary instead of silently coercing.
    """
    ledger: dict[str, dict[str, RepoLedgerEntry]] = {}
    for entry in repo_set:
        if not isinstance(entry, dict):
            continue
        _validate_repo_entry(entry)
        repo_id = entry.get("repo_id") or ""
        if not repo_id:
            continue
        project_path = entry.get("project_path") or ""
        target_name = entry.get("target_name") or ""
        if not target_name:
            ledger[repo_id] = {}
            continue
        session = read_session(
            category, target_name, project_path, quiet_missing=True,
        )
        gate = session.get(GATE_REVIEW_GATE) or {}
        quality = _quality_data_for(category, target_name, project_path)
        doc_dir = Path(doc_dir_path(category, target_name, project_path))

        repo_view: dict[str, RepoLedgerEntry] = {}
        for doc in docs:
            doc = doc.strip()
            if not doc:
                continue
            doc_path = doc_dir / doc
            if not doc_path.is_file():
                continue
            try:
                stale = is_doc_stale(str(doc_path), quality, doc)
            except OSError:
                stale = False
            doc_entry = ((quality.get("documents") or {}).get(
                doc_key(doc),
            )) or {}
            repo_view[doc] = {
                "last_reviewed_at": doc_entry.get("last_reviewed_at"),
                "last_modified_at": os.path.getmtime(doc_path),
                "fix_cycle": int(gate.get(GATE_FIX_CYCLE) or 0),
                "reentry_count": int(gate.get(GATE_REENTRY_COUNT) or 0),
                "stale": bool(stale),
            }
        ledger[repo_id] = repo_view
    return ledger


def stale_repos(ledger: dict[str, dict[str, dict]]) -> list[str]:
    """Return the sorted list of repo IDs with at least one stale doc."""
    return sorted(
        repo_id for repo_id, repo_view in ledger.items()
        if any(d.get("stale") for d in repo_view.values())
    )


def is_any_repo_stale(ledger: dict[str, dict[str, dict]]) -> bool:
    """True iff any repo in *ledger* carries a stale doc."""
    return bool(stale_repos(ledger))
