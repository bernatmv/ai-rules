"""Review quality registry — public API.

Unified import surface bundling constants (``constants.py``) and
registry query helpers (``registry_helpers.py``). Consumers import from
here and reach both layers without picking a sub-module.
"""
from __future__ import annotations

from .constants import (  # noqa: F401
    DOCUMENT_REGISTRY,
    SCHEMA_VERSION,
    SCORE_VALUE_MAP,
    SEMVER_RE,
    _SCRIPT_OWNED_KEYS,
    _STEERING_SIZE_LIMIT,
    VALID_FINDING_TYPES,
    VALID_THOROUGHNESS_RATINGS,
    VALID_SPEC_TYPES,
    VALID_CONFIDENCE_LEVELS,
    PASSING_CONFIDENCE_LEVELS,
    DESIGN_PRINCIPLE_WEIGHT,
    DOC_STATUS_THRESHOLDS,
    TIER1_SCRIPT_SPECS,
    _validate_tier1_completeness,
    empty_issues,
    empty_score,
)

from .registry_helpers import (  # noqa: F401
    all_doc_keys_for_type,
    effective_doc_keys,
    active_doc_keys_from_files,
    cross_validation_pairs_for_type,
    expected_headings_for_stem,
    generate_criteria_skeleton,
    criteria_facet_ids,
    is_valid_finding,
    tier1_facets_for_type,
)
