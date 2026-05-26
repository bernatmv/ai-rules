"""Aggregator re-exports for the builder surface.

Groups the per-concern builders (cross_validation / document_merge /
history / namespace_builders / supplemental / subprocess_checks) under
a single import path so callers compose review-quality payloads
through one module.
"""
from __future__ import annotations

from .cross_validation import _build_cross_validation      # noqa: F401
from .document_merge import merge_documents                 # noqa: F401
from .document_merge import _incomplete_placeholder         # noqa: F401
from .document_merge import _make_facet                     # noqa: F401
from .history import compact_snapshot, build_history        # noqa: F401
from .namespace_builders import BuildContext                # noqa: F401
from .namespace_builders import _CONTEXT_BUILDERS           # noqa: F401
from .namespace_builders import _SUPPLEMENTAL_BUILDERS      # noqa: F401
from .supplemental import _build_testing_thoroughness       # noqa: F401
from .supplemental import _build_design_principles_scorecard  # noqa: F401
from .supplemental import _build_anti_pattern_detections    # noqa: F401
from .subprocess_checks import _check_spec_type             # noqa: F401

def _default_comprehension() -> dict:
    """Return a fresh empty comprehension dict."""
    return {
        "confidence": "LOW",
        "questions_passed": 0,
        "questions_total": 0,
        "full_test_passed": None,
        "questions": [],
        "full_test": None,
    }
