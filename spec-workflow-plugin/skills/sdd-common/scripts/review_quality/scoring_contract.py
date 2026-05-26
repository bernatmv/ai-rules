"""Scoring contract — narrative score derivation from a facet set.

``ScoringContract`` derives both sides of the narrative/authoritative
score from one ``FacetSet`` so the prompt text and the post-review
denominator cannot drift. The prompt template consumes
:meth:`ScoringContract.narrative_instruction` verbatim; the post-review
path consumes :attr:`ScoringContract.canonical_max` for the
``artifact_score.max`` denominator. Callers that just need the
integer ceiling use the :func:`max_for` helper.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from review_quality.registry_helpers import (
    facets_for_doc_keys, tier1_facets_for_type,
)

__all__ = [
    "ScoringContract",
    "scoring_contract_for",
    "build_contract_from_doc_list",
    "max_for",
]


@dataclass(frozen=True)
class ScoringContract:
    doc_key: str
    tier1_facets: tuple[str, ...]
    tier2_facets: tuple[str, ...]

    @property
    def canonical_max(self) -> int:
        """Tier-2 count. The authoritative denominator for both
        narrative and post-review scores."""
        return len(self.tier2_facets)

    def narrative_instruction(self) -> str:
        """Return the ``Report overall as …`` sentence for the prompt."""
        total = self.canonical_max
        if self.tier1_facets:
            tier1_csv = ", ".join(self.tier1_facets)
            tier1_note = (
                f" Tier 1 facets ({tier1_csv}) are reported "
                f"separately and do not contribute to the denominator."
            )
        else:
            tier1_note = ""
        return (
            f"Report overall as {{total}}/{total} across the {total} "
            f"Tier 2 facets.{tier1_note}"
        )

    def tier1_handling_note(self) -> str:
        """Return the instruction naming Tier 1 and Tier 2 facet lists."""
        return (
            f"Tier 1 (script-owned, do NOT include in tier2_scores): "
            f"{list(self.tier1_facets)}\n"
            f"Tier 2 (your responsibility, MUST include in tier2_scores): "
            f"{list(self.tier2_facets)}\n"
        )


def scoring_contract_for(review_type: str, doc_keys: Iterable[str]) -> ScoringContract:
    """Build a contract for the union of ``doc_keys`` under ``review_type``.

    When ``doc_keys`` spans multiple docs (e.g. a final-scope review),
    the contract's Tier 2 facets is the union across all docs;
    ``canonical_max`` is the total count.
    """
    key_set = set(doc_keys)
    facets_by_doc = facets_for_doc_keys(review_type, key_set)
    tier1_ids = tier1_facets_for_type(review_type)

    all_ids: list[str] = []
    for _doc, lst in facets_by_doc.items():
        for f in lst:
            fid = f["id"]
            if fid not in all_ids:
                all_ids.append(fid)

    in_scope_tier1 = tuple(fid for fid in all_ids if fid in tier1_ids)
    tier2 = tuple(fid for fid in all_ids if fid not in tier1_ids)
    doc_key = next(iter(key_set)) if len(key_set) == 1 else "__multi__"
    return ScoringContract(
        doc_key=doc_key,
        tier1_facets=in_scope_tier1,
        tier2_facets=tier2,
    )


def max_for(review_type: str, doc_keys: Iterable[str]) -> int:
    """Return the canonical ``artifact_score.max`` for a doc-key set.

    Thin helper over :func:`scoring_contract_for` so callers can ask
    for the integer ceiling without constructing the full contract.
    """
    return scoring_contract_for(review_type, doc_keys).canonical_max


def build_contract_from_doc_list(
    review_type: str, doc_list: str,
) -> ScoringContract:
    """Resolve filenames in ``doc_list`` to doc-keys, then build a contract.

    Empty / missing ``doc_list`` falls back to the registry's full
    doc-key set — same opt-in filter as the prompt builder.
    """
    from review_quality.registry_helpers import resolve_doc_keys_from_files
    from sdd_core.doc_config import DOCUMENT_REGISTRY

    files = [f.strip() for f in (doc_list or "").split(",") if f.strip()]
    if files:
        keys = resolve_doc_keys_from_files(review_type, files)
    else:
        keys = set(DOCUMENT_REGISTRY[review_type]["doc_keys"])
    return scoring_contract_for(review_type, keys)
