"""Query and utility functions that operate on DOCUMENT_REGISTRY.

Split from registry.py (data-only): data definitions change when
document types change; query functions change when consumers need new
access patterns.
"""
from __future__ import annotations

import os

from sdd_core.doc_config import DOCUMENT_REGISTRY
from .constants import VALID_FINDING_TYPES, TIER1_SCRIPT_SPECS


def all_doc_keys_for_type(review_type: str) -> set:
    """Return the full set of known doc keys (required + optional) for a review type."""
    reg = DOCUMENT_REGISTRY[review_type]
    return set(reg["doc_keys"]) | set(reg.get("optional_doc_keys", []))


def effective_doc_keys(review_type: str, present_keys: set) -> list:
    """Return ordered doc keys: all required plus present optional keys."""
    reg = DOCUMENT_REGISTRY[review_type]
    return list(reg["doc_keys"]) + [
        k for k in reg.get("optional_doc_keys", []) if k in present_keys
    ]


def active_doc_keys_from_files(review_type: str, doc_dir: str) -> list:
    """Return ordered doc_keys that are either required or present on disk.

    Scans *doc_dir* for optional doc files and includes them only if found.
    """
    reg = DOCUMENT_REGISTRY[review_type]
    present = set()
    for key in reg.get("optional_doc_keys", []):
        filename = reg["doc_files"].get(key, "")
        if filename and os.path.isfile(os.path.join(doc_dir, filename)):
            present.add(key)
    return effective_doc_keys(review_type, present)


def cross_validation_pairs_for_type(review_type: str, present_optional_keys: set | None = None) -> list:
    """Return cross-validation pairs, including optional-doc pairs when present."""
    reg = DOCUMENT_REGISTRY[review_type]
    pairs = list(reg.get("cross_validation_pairs", []))
    if present_optional_keys:
        for opt_key, opt_pairs in reg.get("cross_validation_pairs_optional", {}).items():
            if opt_key in present_optional_keys:
                pairs.extend(opt_pairs)
    return pairs


def canonical_cross_validation_keys(review_type: str) -> set[str]:
    """Canonical ``<a>_x_<b>`` pair keys for *review_type*.

    Includes both orderings — pair-key equality is order-insensitive.
    """
    pairs = cross_validation_pairs_for_type(review_type)
    return (
        {f"{a}_x_{b}" for (a, b) in pairs}
        | {f"{b}_x_{a}" for (a, b) in pairs}
    )


def resolve_doc_keys_from_files(review_type: str, files: list[str]) -> set:
    """Map doc filenames (``tech.md``) back to registry doc_keys (``tech_md``).

    Unknown entries pass through unchanged so the caller still sees the
    raw token when the list mixes filenames and doc_keys. Empty /
    whitespace-only entries are dropped to keep the resulting set tidy.
    """
    reg = DOCUMENT_REGISTRY[review_type]
    file_to_key = {v: k for k, v in reg.get("doc_files", {}).items()}
    result: set = set()
    for f in files:
        token = (f or "").strip()
        if not token:
            continue
        result.add(file_to_key.get(token, token))
    return result


def facets_for_doc_keys(review_type: str, doc_keys: set) -> dict:
    """Return facet lists filtered to the supplied ``doc_keys``.

    Empty ``doc_keys`` falls through to the full registry map so callers
    that pass no scope (code review, full steering review) keep the
    current behaviour — the filter is opt-in.
    """
    reg = DOCUMENT_REGISTRY[review_type]
    facets_map = reg.get("facets", {})
    if not doc_keys:
        return dict(facets_map)
    return {k: v for k, v in facets_map.items() if k in doc_keys}


from sdd_core.doc_config import expected_headings_for_stem  # noqa: F811,E402,F401 — canonical impl lives in doc_config


def generate_criteria_skeleton(review_type: str, doc_key: str) -> str:
    """Generate a validation-criteria markdown skeleton from registry facets.

    Useful for bootstrapping new criteria files and detecting drift between
    the registry (single source of truth) and the criteria markdown files.
    """
    reg = DOCUMENT_REGISTRY[review_type]
    filename = reg["doc_files"].get(doc_key, f"{doc_key}.md")
    facets = reg["facets"].get(doc_key, [])
    lines = [f"# {filename} Validation Criteria", ""]
    for i, facet in enumerate(facets, 1):
        lines.append(f"### {i}. {facet['name']}")
        lines.append("")
        lines.append("**Pass:**")
        lines.append("- [criteria to be defined]")
        lines.append("")
        lines.append("**Fail:**")
        lines.append("- [criteria to be defined]")
        lines.append("")
    return "\n".join(lines)


def criteria_facet_ids(review_type: str, doc_key: str) -> list[str]:
    """Return ordered facet IDs for a doc, useful for validating criteria files."""
    reg = DOCUMENT_REGISTRY[review_type]
    return [f["id"] for f in reg["facets"].get(doc_key, [])]


def is_valid_finding(finding: dict) -> bool:
    """Check that a finding has a recognized type and non-empty summary."""
    return (
        isinstance(finding, dict)
        and finding.get("type") in VALID_FINDING_TYPES
        and isinstance(finding.get("summary"), str)
        and bool(finding["summary"].strip())
    )


def tier1_facets_for_type(review_type: str) -> set[str]:
    """Return set of Tier 1 facet IDs for a review type."""
    return {
        facet_id
        for script_name in DOCUMENT_REGISTRY[review_type]["tier1_scripts"]
        for facet_id in TIER1_SCRIPT_SPECS[script_name]["covers"]
    }
