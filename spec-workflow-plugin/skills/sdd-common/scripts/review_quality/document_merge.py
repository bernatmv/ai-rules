"""Document block assembly — merging, placeholders, facet construction."""
from __future__ import annotations

from sdd_core.review_input import (
    INPUT_KEY_DOCUMENTS_REVIEWED,
    INPUT_KEY_TIER2_SCORES,
)
from sdd_core.status import DocStatus

from .registry import (
    DOCUMENT_REGISTRY, SCORE_VALUE_MAP,
    empty_issues, empty_score,
    tier1_facets_for_type,
    all_doc_keys_for_type, effective_doc_keys,
)
from .scoring import recompute_doc_score, derive_doc_status
from .scoring_contract import max_for
from .constants import STRUCTURAL_NA_PREFIX
from .facet_predicates import SpecMeta, evaluate as evaluate_predicate


def _normalize_issues(raw: dict | None) -> dict[str, int]:
    """Coerce issues values to int counts. Handles arrays (len) for resilience."""
    base = empty_issues()
    if not raw or not isinstance(raw, dict):
        return base
    for sev in ("critical", "warning", "suggestion"):
        val = raw.get(sev, 0)
        if isinstance(val, list):
            base[sev] = len(val)
        elif isinstance(val, (int, float)):
            base[sev] = int(val)
    return base


def _make_facet(
    facet_id: str,
    facet_name: str,
    score: str,
    issues: dict[str, int] | None = None,
    na_justification: str | None = None,
) -> dict:
    """Build a single facet dict with consistent structure.

    ``na_justification`` travels with the facet when the sub-agent
    explicitly scored ``na`` with a reason. Auto-inserted "missing
    facet" placeholders (no justification) still render as ``na`` but
    are treated differently by :func:`recompute_doc_score` — justified
    ``na`` entries count toward the denominator so a sub-agent cannot
    inflate percent by marking difficult facets ``na``.
    """
    facet = {
        "id": facet_id,
        "name": facet_name,
        "score": score,
        "score_value": SCORE_VALUE_MAP.get(score),
        "issues": _normalize_issues(issues),
    }
    if na_justification:
        justification = str(na_justification).strip()
        if justification:
            facet["na_justification"] = justification
    return facet


def _incomplete_placeholder(review_type: str, doc_key: str) -> dict:
    doc_registry = DOCUMENT_REGISTRY[review_type]
    placeholder: dict = {
        "file": doc_registry["doc_files"].get(doc_key, f"{doc_key}.md"),
        "status": DocStatus.INCOMPLETE,
        "last_reviewed_at": None,
        "score": empty_score(),
        "line_count": None,
        "template_compliance": DocStatus.INCOMPLETE,
        "facets": [],
    }
    for field, spec in doc_registry.get("extra_doc_fields", {}).items():
        placeholder[field] = spec["default"]
    return placeholder


def _tier2_only(facets: list[dict], tier1_ids: set[str]) -> list[dict]:
    """Return the Tier 2 subset of *facets*.

    The scoring contract says Tier 1 is reported separately and does
    not contribute to ``artifact_score`` — the denominator is the
    Tier 2 facet count (see :class:`review_quality.scoring_contract.
    ScoringContract`). Filtering at this boundary keeps
    :func:`recompute_doc_score` agnostic of tier semantics.
    """
    return [f for f in facets if f.get("id") not in tier1_ids]


def _apply_canonical_max(
    doc_score: dict, review_type: str, doc_key: str,
    *, structural_na_count: int = 0,
) -> dict:
    """Return ``doc_score`` with ``max`` pinned to the canonical ceiling.

    ``recompute_doc_score`` derives ``max`` from the per-facet list;
    the canonical Tier 2 ceiling lives in :func:`max_for`. When the
    two agree nothing changes. When they disagree (missing facets,
    legacy artifact shapes), the canonical ceiling wins and ``percent``
    is recomputed so ``value / max`` stays consistent.

    ``structural_na_count`` shrinks the canonical ceiling by the
    number of facets dropped via :data:`STRUCTURAL_NA_PREFIX` so the
    denominator stays consistent with
    :func:`recompute_doc_score`'s output.
    """
    canonical_max = max_for(review_type, [doc_key]) - structural_na_count
    if canonical_max < 0:
        canonical_max = 0
    if doc_score.get("max") == canonical_max:
        return doc_score
    value = doc_score.get("value", 0)
    percent = round(value / canonical_max * 100) if canonical_max > 0 else 0
    return {"value": value, "max": canonical_max, "percent": percent}


def merge_documents(
    input_data: dict,
    tier1_results: dict,
    prior: dict | None,
    review_type: str,
    now: str,
    *,
    spec_meta: SpecMeta | None = None,
) -> tuple[dict, list[str]]:
    """Build document blocks, merging new review with prior state.

    Returns (documents dict, reviewed_keys list).

    ``spec_meta`` carries the inputs the structural-na predicates
    consult (see :mod:`review_quality.facet_predicates`). When
    omitted, the predicate evaluator returns ``False`` and every facet
    keeps its current scoring weight — no behaviour change for legacy
    callers.
    """
    doc_registry = DOCUMENT_REGISTRY[review_type]
    reviewed_keys_raw = input_data.get(INPUT_KEY_DOCUMENTS_REVIEWED, [])
    known_keys = all_doc_keys_for_type(review_type)
    reviewed_keys = [k for k in reviewed_keys_raw if k in known_keys]
    tier2_scores_by_doc = input_data.get(INPUT_KEY_TIER2_SCORES, {})
    prior_docs = (prior.get("documents") or {}) if prior else {}
    tier1_ids = tier1_facets_for_type(review_type)
    documents: dict[str, dict] = {}

    active_keys = effective_doc_keys(
        review_type, set(reviewed_keys) | set(prior_docs),
    )

    for doc_key in active_keys:
        filename = doc_registry["doc_files"][doc_key]
        facet_defs = doc_registry["facets"].get(doc_key, [])
        facet_def_by_id = {f["id"]: f["name"] for f in facet_defs}

        if doc_key in reviewed_keys:
            tier1_doc = tier1_results.get(doc_key, {})
            tier2_entries_raw = tier2_scores_by_doc.get(doc_key, []) or []
            tier2_map: dict[str, dict] = {}
            for entry in tier2_entries_raw:
                facet_id = entry.get("id", "")
                if facet_id in tier1_ids or facet_id not in facet_def_by_id:
                    continue
                tier2_map[facet_id] = entry

            tier1_facet_scores = tier1_doc.get("tier1_facets", {})
            structural_na_in_doc = 0
            facets: list[dict] = []
            for fdef in facet_defs:
                facet_id = fdef["id"]
                facet_name = fdef["name"]
                predicate_name = fdef.get("structural_na_when")
                is_structural_na = (
                    predicate_name is not None
                    and facet_id not in tier1_ids
                    and evaluate_predicate(predicate_name, spec_meta)
                )
                if facet_id in tier1_ids:
                    score = tier1_facet_scores.get(facet_id, "na")
                    issues = empty_issues()
                    if score == "fail":
                        issues["critical"] = 1
                    facets.append(_make_facet(facet_id, facet_name, score, issues))
                elif is_structural_na:
                    structural_na_in_doc += 1
                    facets.append(_make_facet(
                        facet_id, facet_name, "na",
                        na_justification=f"{STRUCTURAL_NA_PREFIX} {predicate_name}",
                    ))
                else:
                    entry = tier2_map.get(facet_id)
                    if entry:
                        facets.append(_make_facet(
                            facet_id, facet_name, entry["score"],
                            entry.get("issues", empty_issues()),
                            na_justification=entry.get("na_justification"),
                        ))
                    else:
                        facets.append(_make_facet(facet_id, facet_name, "na"))

            doc_score = _apply_canonical_max(
                recompute_doc_score(_tier2_only(facets, tier1_ids)),
                review_type, doc_key,
                structural_na_count=structural_na_in_doc,
            )
            doc_status = derive_doc_status(doc_score, facets)
            doc_block: dict = {
                "file": filename,
                "status": doc_status,
                "last_reviewed_at": now,
                "score": doc_score,
                "line_count": tier1_doc.get("line_count"),
                "template_compliance": tier1_doc.get("template_compliance", DocStatus.INCOMPLETE),
                "facets": facets,
            }
            for field, fspec in doc_registry.get("extra_doc_fields", {}).items():
                doc_block[field] = tier1_doc.get(fspec["tier1_key"], fspec["default"])
            documents[doc_key] = doc_block

        elif doc_key in prior_docs:
            documents[doc_key] = prior_docs[doc_key]
        elif doc_key not in doc_registry.get("optional_doc_keys", []):
            documents[doc_key] = _incomplete_placeholder(review_type, doc_key)

    return documents, reviewed_keys
