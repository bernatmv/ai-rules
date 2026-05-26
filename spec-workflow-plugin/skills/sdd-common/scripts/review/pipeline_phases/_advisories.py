"""Pure detection helpers for review-pipeline advisories.

No I/O, no envelope emission. Callers receive a structured dict (or
``None``) and decide which envelope slot — ``data.advisories[]`` or a
dedicated ``output.partial`` payload — to surface it on. Splitting
detection from emission keeps the pure getters in :mod:`scoring_io`
side-effect-free.

Underscore prefix excludes this module from the ``@phase`` registry
import loop in :mod:`review.pipeline_phases.__init__`.
"""
from __future__ import annotations

from typing import Iterable

from sdd_core import review_quality_schema as rq


_ADVISORY_KIND_V3_READER_DRIFT = "schema_v3_reader_drift"


def detect_v3_reader_drift(
    data: dict | None,
    scope: str,
    doc_keys: Iterable[str],
) -> dict | None:
    """Return a ``schema_v3_reader_drift`` advisory or ``None``.

    Predicate (all must hold):
    - *data* is a non-empty dict tagged ``schema_version == 3``;
    - at least one ``by_scope.per-document.<doc_key>`` slot is populated
      (or any per-doc slot when *doc_keys* is empty);
    - the populated slot's ``overall_score`` is NOT present in
      ``rq.get_active(data)``.

    Caller pre-condition: ``read_scoped_score`` has already returned
    ``None`` for the same *data* / *scope* / *doc_keys* tuple. The
    helper does not re-derive that signal.

    Caller emits via ``output.partial(...)`` (or attaches the dict to an
    existing emission envelope). This helper does no I/O.
    """
    if not isinstance(data, dict) or not data:
        return None
    if data.get("schema_version") != rq.SCHEMA_VERSION:
        return None

    requested_keys = [k for k in (doc_keys or ()) if isinstance(k, str) and k]
    candidate_keys = list(requested_keys)
    if not candidate_keys:
        candidate_keys = list(rq.iter_per_document_keys(data))

    active = rq.get_active(data)
    active_overall = active.get("overall_score") if isinstance(active, dict) else None

    for key in candidate_keys:
        slot = rq.get_by_scope(data, rq.PER_DOCUMENT_SCOPE, key)
        if not isinstance(slot, dict) or not slot:
            continue
        slot_overall = slot.get("overall_score")
        if slot_overall is None:
            continue
        if active_overall is not None and slot_overall == active_overall:
            continue
        return {
            "advisory": _ADVISORY_KIND_V3_READER_DRIFT,
            "summary": (
                f"v3 per-document slot {key} is populated but not "
                "visible to reader"
            ),
            "fix_hint": (
                "scoring_io reader must consult by_scope.per-document."
                "<key> for this scope."
            ),
            "details": {"doc_key": key, "scope": rq.PER_DOCUMENT_SCOPE},
        }
    return None
