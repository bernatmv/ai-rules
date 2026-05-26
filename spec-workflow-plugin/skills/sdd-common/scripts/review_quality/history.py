"""History/snapshot construction."""
from __future__ import annotations

from sdd_core.review_input import INPUT_KEY_CROSS_VALIDATION
from sdd_core.status import DocStatus

from .registry import empty_score, effective_doc_keys


def compact_snapshot(state: dict, review_type: str) -> dict:
    """Extract a compact history snapshot from a full artifact state."""
    comp = state.get("comprehension") or {}
    comprehension_confidence = comp.get("confidence") if comp else None
    cv = state.get(INPUT_KEY_CROSS_VALIDATION)
    cv_status = cv.get("status") if cv else None
    docs_compact: dict[str, dict] = {}
    state_docs = state.get("documents") or {}
    all_state_doc_keys = effective_doc_keys(review_type, set(state_docs))
    for doc_key in all_state_doc_keys:
        doc = state_docs.get(doc_key, {})
        docs_compact[doc_key] = {
            "status": doc.get("status", DocStatus.INCOMPLETE),
            "score": doc.get("score", empty_score()),
        }
    return {
        "at": state.get("generated_at"),
        "overall_status": state.get("overall_status", DocStatus.INCOMPLETE),
        "overall_score": state.get("overall_score"),
        "cross_validation_status": cv_status,
        "comprehension_confidence": comprehension_confidence,
        "documents": docs_compact,
    }


def build_history(merged: dict, prior: dict | None, review_type: str) -> dict:
    """Build history block by appending current run snapshot to runs array."""
    current_snapshot = compact_snapshot(merged, review_type)
    if prior is None:
        return {"runs": [current_snapshot]}
    prior_history = prior.get("history") or {}
    prior_runs = prior_history.get("runs") or []
    return {"runs": prior_runs + [current_snapshot]}
