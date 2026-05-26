"""Public types, constants, and data locations for the validator.

Co-located with the package so both the ruleset loader and the test
support helpers import ``DATA_FILE`` from a single place — no
path duplication between source and tests.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import TypedDict

__all__ = [
    "CANONICAL_GROUPS",
    "CANONICAL_GROUPS_SET",
    "BANNER_GROUP_HOOKS",
    "GROUP_FIX_HINTS",
    "NON_SUPPRESSIBLE_GROUPS",
    "REPLACEMENT_PLACEHOLDERS",
    "SUPPRESSION_ALIASES",
    "DATA_FILE",
    "MODE_STANDARD",
    "MODE_BUG_FIX",
    "VALID_MODES",
    "SUPPRESSION_TAG_RE",
    "Finding",
    "ValidationOutcome",
    "STRATEGY_REGEX",
    "STRATEGY_WORD",
    "NESTED_WORD_BUCKETS",
]

# Data location — owned by this module so the test-support validator
# pulls it from the same import rather than recomputing the path.
DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "requirements_antipatterns.yaml"

MODE_STANDARD = "standard"
MODE_BUG_FIX = "bug-fix"
VALID_MODES = frozenset({MODE_STANDARD, MODE_BUG_FIX})

# Accept both ``rq-ignore: tech-stack`` and ``rq-ignore: Tech-Stack``.
# The captured group is lower-cased in ``_collect_suppressions`` so
# storage stays canonical.
SUPPRESSION_TAG_RE = re.compile(
    r"<!--\s*rq-ignore:\s*(?P<group>[A-Za-z-]+)\s*-->"
)

# Canonical group names. Runtime code (sort key) uses the ordered tuple;
# dev-time validators (``tests/_support/antipattern_data_validator.py``)
# pull the frozenset alias for schema membership checks. Single source of
# truth — do not re-declare elsewhere.
CANONICAL_GROUPS: tuple[str, ...] = (
    "structural", "path", "code", "tech-stack", "api-config",
    "architecture-concepts", "architecture-impl",
)
CANONICAL_GROUPS_SET: frozenset[str] = frozenset(CANONICAL_GROUPS)

# Coarse-grained ``rq-ignore`` tags expand into the fine-grained
# canonical group set. One entry per coarse tag → the set of canonical
# groups it aliases.
# ``architecture-concepts`` is deliberately excluded — see
# :data:`NON_SUPPRESSIBLE_GROUPS` for the authority on groups that cannot
# be cleared via ``rq-ignore``.
SUPPRESSION_ALIASES: dict[str, frozenset[str]] = {
    "architecture": frozenset({"architecture-impl"}),
}

# Groups whose findings can never be cleared by an ``rq-ignore`` comment.
# ``architecture-concepts`` lives here because the workspace template
# must stay clean of engineering-principle jargon — validator and
# reviewer agree on every line of the canonical template. Suppressing
# the sentinel would reintroduce the drift.
NON_SUPPRESSIBLE_GROUPS: frozenset[str] = frozenset({"architecture-concepts"})

# Fallback fix hints per canonical group. The per-rule YAML ``suggestion``
# takes precedence when set; these cover rules without inline suggestions
# so agents always receive something actionable. Co-located with
# :data:`CANONICAL_GROUPS` so the parity assertion below catches drift
# at import time — a new canonical group must ship with a matching hint.
GROUP_FIX_HINTS: dict[str, str] = {
    "structural": "Add the missing structural element (heading / user story / acceptance criterion).",
    "path": "Drop the path reference; describe what the user does, not where code lives.",
    "code": "Express the requirement as user-facing behaviour, not code.",
    "tech-stack": "Rephrase as a constraint on observable behaviour (latency, availability).",
    "api-config": "Describe the outcome the user sees, not the wire format.",
    "architecture-concepts": "Move engineering principles to design.md; describe user-facing behaviour here.",
    "architecture-impl": "Prefer user-facing framing; implementation-layer terms belong in design.md.",
}

assert set(GROUP_FIX_HINTS) == CANONICAL_GROUPS_SET, (  # noqa: S101 — intentional import-time guard
    "GROUP_FIX_HINTS keys must match CANONICAL_GROUPS; "
    f"missing={CANONICAL_GROUPS_SET - set(GROUP_FIX_HINTS)}, "
    f"extra={set(GROUP_FIX_HINTS) - CANONICAL_GROUPS_SET}"
)


# Placeholder tokens that the runtime renderer substitutes into the
# YAML ``replacement_template`` field at finding-emission time. The
# YAML schema validator (``tests/_support/antipattern_data_validator``)
# imports the same set so authoring a template referencing a token
# absent from this constant fails at validation time.
# Why: keeping one canonical set means a future placeholder addition
# lands one-line in this module rather than two locations drifting.
REPLACEMENT_PLACEHOLDERS: frozenset[str] = frozenset({"match", "section"})


# YAML group id → substring expected in
# ``references/requirements-antipatterns.md``. The reference doc is
# the canonical home for the rule list (the in-template banner was
# retired in favour of a one-line pointer); this map keeps the parity
# test honest when a YAML group is added without a matching reference
# section.
BANNER_GROUP_HOOKS: dict[str, str] = {
    "path": "`path`",
    "code": "`code`",
    "tech-stack": "`tech-stack`",
    "api-config": "`api-config`",
    "architecture-concepts": "`architecture-concepts`",
    "architecture-impl": "`architecture-impl`",
    "structural": "`structural`",
}


class Finding(TypedDict, total=False):
    """Wire-typed dict representing one validator finding.

    ``TypedDict`` gives static typing (IDE completion, type checkers) while
    keeping the runtime shape a plain dict — no custom ``__init__`` or
    class state. Keys use ``total=False`` because not every emission site
    sets every field (``suggestion`` is often ``None``).

    ``replacement_text`` is the rendered ``replacement_template`` for
    the rule — present only when the YAML rule declares one. Surfaced
    so downstream consumers (pre-launch-check, post-fix) can present a
    literal substitution suggestion the agent applies mechanically.
    """

    severity: str
    group: str
    rule: str
    line: int
    column: int
    section: str
    match: str
    message: str
    suggestion: "str | None"
    replacement_text: "str | None"


class ValidationOutcome(TypedDict):
    """Top-level validator result: counts, findings, and mode."""

    mode: str
    result: str
    counts: dict[str, int]
    issues: list[Finding]


# Match strategies recognised for data-driven dispatch in
# :func:`line_findings.iter_line_findings`.
STRATEGY_REGEX = "regex"
STRATEGY_WORD = "word-matcher"

# Nested word-matcher buckets declared inside a group body. Kept as a
# known set so ``tests/_support/antipattern_data_validator.py`` and
# the line-findings dispatcher agree on the vocabulary.
NESTED_WORD_BUCKETS = ("env_var_literals", "package_managers")
