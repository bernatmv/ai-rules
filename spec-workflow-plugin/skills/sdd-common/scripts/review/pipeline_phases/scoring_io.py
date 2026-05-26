"""Artifact score I/O and line counting for pipeline phases.

Score scales:
- Sub-agent prompt uses a 15-point scale (5 facets x 3 points) for clear
  arithmetic instructions to the LLM.
- Artifact stores a normalized per-document 5-point scale (5 facets x 1 point)
  for cross-document comparability.
- post_review phase reads ONLY the artifact scale. Sub-agent narrative scores
  are intentionally ignored.

All envelope-shape access routes through
:mod:`sdd_core.review_quality_schema` accessors. Direct
``data["by_scope"]`` / ``data.get("documents")`` reads are reserved for
the schema module.
"""
from __future__ import annotations

from typing import Iterator

from review_quality.constants import (
    REVIEW_QUALITY_FILENAME,
    PASS_THRESHOLD_PCT,
    NEEDS_WORK_THRESHOLD_PCT,
    DEFAULT_REVIEW_SCOPE,
)

from review_quality.staleness import doc_key
from sdd_core import review_quality_schema as rq


def count_effective_lines(filepath: str) -> int:
    """Count effective lines (non-empty, non-frontmatter) in a document."""
    from skill_helpers import iter_effective_lines
    return sum(1 for _ in iter_effective_lines(filepath))


def quality_file_path(category: str, target_name: str, project_path: str) -> str:
    """Return the absolute path to review-quality.json for the given target."""
    from sdd_core.paths import doc_dir_path
    import os
    return os.path.join(
        doc_dir_path(category, target_name, project_path),
        REVIEW_QUALITY_FILENAME,
    )


def load_quality_data(
    category: str, target_name: str, project_path: str,
) -> dict | None:
    """Load and validate review-quality.json once. Returns parsed dict or None."""
    from sdd_core import output as _output
    data = _output.safe_read_json(
        quality_file_path(category, target_name, project_path), default=None,
    )
    if not data or not isinstance(data, dict):
        return None
    return data


def _normalize_score(overall: dict | None, status: str | None) -> dict | None:
    """Return a consistent {value, max, percent, status} dict without mutating the source."""
    if not overall or not isinstance(overall, dict):
        return None
    return {
        "value": overall.get("value", 0),
        "max": overall.get("max", 0),
        "percent": overall.get("percent", 0),
        "status": status,
    }


def _split_doc_keys(doc_list: str) -> set[str]:
    """Parse a comma-separated ``doc_list`` into a set of doc keys.

    The CLI surfaces the list as a comma-separated string of filenames
    (``"requirements.md,tasks.md"``); this helper canonicalises each
    entry through :func:`review_quality.staleness.doc_key` so callers
    consistently key into the v3 ``by_scope.per-document`` bucket.
    Empty / blank input yields the empty set.
    """
    return {
        doc_key(k.strip()) for k in (doc_list or "").split(",") if k.strip()
    }


def _candidate_active_views(
    data: dict, *, scope: str, doc_keys: set[str],
) -> Iterator[dict]:
    """Yield active-shaped snapshots applicable to the requested scope.

    Order of preference:

    1. Top-level ``active`` (the v3 promotion target — e.g. final-scope
       gate or last-promoted per-doc cycle).
    2. v3 ``by_scope.per-document.<key>`` slots when *scope* is
       ``"per-document"`` (or ``"full"`` falling back to the per-doc
       siblings — disabled here; the caller decides).

    The function is read-only: each yielded view is the slot dict from
    the schema accessor, and callers must not mutate it.
    """
    active = rq.get_active(data)
    if active:
        yield active
    if scope == DEFAULT_REVIEW_SCOPE:
        for key in rq.iter_per_document_keys(data):
            if doc_keys and key not in doc_keys:
                continue
            slot = rq.get_by_scope(data, rq.PER_DOCUMENT_SCOPE, key)
            if slot:
                yield slot


def view_active_documents(legacy_envelope: dict | None) -> dict:
    """Return the ``documents`` map for v1/v2 artifacts, or ``{}`` for v3.

    v3 routes the same data through ``by_scope.per-document``; callers
    walk ``rq.iter_per_doc_active_views(data)`` instead.
    """
    if not isinstance(legacy_envelope, dict):
        return {}
    if legacy_envelope.get("schema_version") == rq.SCHEMA_VERSION:
        return {}
    documents = legacy_envelope.get("documents")
    return documents if isinstance(documents, dict) else {}


def _legacy_top_level_overall(legacy_envelope: dict) -> dict | None:
    """Return ``{value, max, percent, status}`` from a pre-v3 envelope.

    Pre-v3 artifacts kept ``overall_score`` / ``overall_status`` at the
    top level; this helper isolates the legacy read so callers stay on
    the schema API for v3.
    """
    return _normalize_score(
        legacy_envelope.get("overall_score"),
        legacy_envelope.get("overall_status"),
    )


def read_artifact_score(
    category: str, target_name: str, project_path: str,
    *, data: dict | None = None,
) -> dict | None:
    """Read overall score from review-quality.json artifact.

    Returns {value, max, percent, status} or None if artifact missing.
    Thin wrapper around ``read_scoped_score`` with scope="full".
    Accepts optional pre-loaded *data* to avoid redundant file reads.
    """
    return read_scoped_score(
        category, target_name, project_path, scope="full", data=data,
    )


def read_scoped_score(
    category: str, target_name: str, project_path: str,
    *, scope: str = "full", doc_list: str = "",
    data: dict | None = None,
) -> dict | None:
    """Return the best available score for the given review scope.

    Resolution order:

    1. Top-level ``overall_score`` / ``active.overall_score`` (final
       gate or promoted per-doc cycle).
    2. ``scope == "per-document"``: walk ``by_scope.per-document`` for
       slots whose key matches *doc_list*, sum each slot's
       ``overall_score`` to a synthetic score.
    3. Legacy v1/v2 ``documents.<key>.score`` aggregation.

    Accepts optional pre-loaded *data* to avoid redundant file reads.
    Returns {value, max, percent, status} or None when no slot satisfies
    the requested scope.
    """
    if data is None:
        data = load_quality_data(category, target_name, project_path)
    if data is None:
        return None

    # 1) Promoted active (v3) or top-level overall (v1/v2).
    active = rq.get_active(data)
    overall = _normalize_score(
        active.get("overall_score") if active else None,
        active.get("overall_status") if active else None,
    )
    if not overall and data.get("schema_version") != rq.SCHEMA_VERSION:
        # Pre-v3 artifacts kept overall_score at the top level. The schema
        # upgrader hoists it onto active when loaded through ``rq.load``;
        # this branch covers the already-loaded-not-upgraded path used by
        # some callers (route through the legacy-named helper so the lint
        # contract stays single-sourced).
        overall = _legacy_top_level_overall(data)
    if overall:
        return overall

    target_keys = _split_doc_keys(doc_list)

    # 2) v3 per-document slots.
    if scope == DEFAULT_REVIEW_SCOPE:
        slot_value, slot_max = 0.0, 0.0
        slot_status_seen: set[str] = set()
        for key in rq.iter_per_document_keys(data):
            if target_keys and key not in target_keys:
                continue
            slot = rq.get_by_scope(data, rq.PER_DOCUMENT_SCOPE, key)
            slot_overall = slot.get("overall_score") if isinstance(slot, dict) else None
            if isinstance(slot_overall, dict):
                slot_value += slot_overall.get("value", 0) or 0
                slot_max += slot_overall.get("max", 0) or 0
            slot_status = slot.get("overall_status") if isinstance(slot, dict) else None
            if isinstance(slot_status, str):
                slot_status_seen.add(slot_status)
        if slot_max > 0:
            return _derive_score_envelope(
                slot_value, slot_max, slot_status_seen,
            )

    # 3) Legacy v1/v2 documents map.
    docs = view_active_documents(data)
    if not docs:
        return None

    value, max_score = 0.0, 0.0
    for key, doc in docs.items():
        if not isinstance(doc, dict):
            continue
        if target_keys and key not in target_keys:
            continue
        score = doc.get("score")
        if score and isinstance(score, dict):
            value += score.get("value", 0)
            max_score += score.get("max", 0)

    if max_score == 0:
        return None

    return _derive_score_envelope(value, max_score, set())


def _derive_score_envelope(
    value: float, max_score: float, statuses: set[str],
) -> dict:
    percent = round(value / max_score * 100, 1) if max_score else 0
    if percent >= PASS_THRESHOLD_PCT:
        derived_status = "PASS"
    elif percent >= NEEDS_WORK_THRESHOLD_PCT:
        derived_status = "NEEDS_WORK"
    else:
        derived_status = "FAIL"
    # If every per-slot status agrees, propagate it; otherwise stick with
    # the percent-derived status so the aggregate stays self-consistent.
    if len(statuses) == 1:
        only = next(iter(statuses))
        if only in {"PASS", "NEEDS_WORK", "FAIL"}:
            derived_status = only
    return {
        "value": value, "max": max_score,
        "percent": percent, "status": derived_status,
    }
