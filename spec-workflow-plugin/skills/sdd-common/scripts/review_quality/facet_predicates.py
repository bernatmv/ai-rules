"""Predicate registry for ``structural_na_when`` facet rules.

Each predicate accepts a :class:`SpecMeta` and returns ``bool``. A
``True`` return signals that the facet is structurally inapplicable to
the spec under review and should be dropped from both the numerator
and denominator of the artifact score (see
:func:`review_quality.scoring.recompute_doc_score`).

Adding a new structural-na rule is two edits:

1. Append a new predicate function below.
2. Register it in :data:`PREDICATES` and reference its name from a
   facet's ``structural_na_when`` key in
   :mod:`sdd_core.doc_config`.

No predicate touches I/O — all state lands on :class:`SpecMeta` so the
facet evaluator stays a pure function and tests can construct meta
fixtures directly.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

__all__ = [
    "SpecMeta",
    "PREDICATES",
    "evaluate",
    "additive_only_feature",
]


@dataclass(frozen=True)
class SpecMeta:
    """Inputs the structural-na predicates consult.

    ``review_type`` is the registry key (``"spec"`` / ``"steering"`` /
    ``"prd"``). ``spec_type`` is the detected spec mode (``"standard"``
    or ``"bug-fix"``). ``has_removals`` is true when the working tree
    diff against the branch base shows any deleted files — the only
    signal needed to decide whether removal/parity facets apply.
    """

    spec_name: str = ""
    spec_type: str = "standard"
    review_type: str = ""
    has_removals: bool = False


def additive_only_feature(meta: SpecMeta) -> bool:
    """True when the spec proposes no removals.

    Removal/parity facets exist to catch behaviour-loss when a feature
    deletes existing code. A purely additive feature (no deletions in
    the working diff) cannot trigger that risk class — those facets
    are structurally inapplicable and should not pad the denominator.
    """
    if meta.review_type != "spec":
        return False
    return not meta.has_removals


PREDICATES: dict[str, Callable[[SpecMeta], bool]] = {
    "additive_only_feature": additive_only_feature,
}


def evaluate(name: str | None, meta: SpecMeta | None) -> bool:
    """Evaluate the named predicate against ``meta``.

    Returns ``False`` when ``name`` is unknown, ``meta`` is missing,
    or the predicate itself fails coercion. The default-false posture
    keeps an unknown registry entry from accidentally suppressing a
    real facet.
    """
    if not name or meta is None:
        return False
    fn = PREDICATES.get(name)
    if fn is None:
        return False
    # Narrow swallow — the failure classes a predicate can legitimately
    # raise: wrong arg shape (TypeError), missing field on SpecMeta
    # (AttributeError), bool coercion failure (ValueError). Every
    # facet evaluation hits this path; surfacing the traceback would
    # dwarf legitimate gate output. Anything outside this set
    # (MemoryError, KeyboardInterrupt) propagates by design.
    try:
        return bool(fn(meta))
    except (TypeError, AttributeError, ValueError):
        return False
