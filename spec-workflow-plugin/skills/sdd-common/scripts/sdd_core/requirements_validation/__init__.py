"""Requirements.md antipattern validation — public API facade.

Thin CLI wrapper lives at ``spec/lint-requirements.py``.

Rules and severities are defined in
``sdd_core/data/requirements_antipatterns.yaml`` (single source of truth).
The human-readable mirror is
``sdd-common/references/requirements-antipatterns.md``.

The package is intentionally small: each submodule owns one stage of
the validator pipeline (types / ruleset / section-maps / line findings /
structural findings / messages / orchestration). Prefer importing from
this facade — submodule boundaries may shift, but the public surface
stays stable.

Reuses existing ``sdd_core`` abstractions exclusively:
  * :class:`sdd_core.matchers.WordMatcher` — tech sentinels, env-var
    literals, architecture jargon.
  * :func:`sdd_core.text.iter_content_lines` — code-fence-aware iteration.
  * :func:`sdd_core.text.extract_sections` — NFR-section lookup for
    section-aware severity.
  * :class:`sdd_core.validation_helpers.Severity` — shared enum.
  * :data:`sdd_core.specs.BUG_FIX_WORDS` / :func:`sdd_core.specs.is_bug_fix_spec`
    — bug-fix detection.
  * ``sdd_core.output`` — JSON envelope emission.
"""
from __future__ import annotations

from .findings_view import build_structured_findings
from .guardrails import iter_error_rules
from .ruleset import load_ruleset
from .types import (
    CANONICAL_GROUPS,
    CANONICAL_GROUPS_SET,
    DATA_FILE,
    Finding,
    GROUP_FIX_HINTS,
    MODE_BUG_FIX,
    MODE_STANDARD,
    SUPPRESSION_ALIASES,
    SUPPRESSION_TAG_RE,
    ValidationOutcome,
)
from .validate import validate_content

__all__ = [
    "CANONICAL_GROUPS",
    "CANONICAL_GROUPS_SET",
    "GROUP_FIX_HINTS",
    "SUPPRESSION_ALIASES",
    "DATA_FILE",
    "MODE_STANDARD",
    "MODE_BUG_FIX",
    "SUPPRESSION_TAG_RE",
    "Finding",
    "ValidationOutcome",
    "build_structured_findings",
    "iter_error_rules",
    "load_ruleset",
    "validate_content",
]
