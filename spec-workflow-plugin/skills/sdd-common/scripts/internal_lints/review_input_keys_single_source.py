#!/usr/bin/env python3
"""Lint: enforce single source for sub-agent input top-level keys.

The five top-level keys in :class:`sdd_core.review_input.SubAgentAssessmentInput`
appear only in :mod:`sdd_core.review_input` (canonical owner),
:mod:`sdd_core.review_quality_schema` (schema-side key constants), and
test fixtures. Re-duplicating any of these literals in another module
recreates the prompt-instruction-vs-script-parser drift the typed
contract collapses.

Usage:
  review_input_keys_single_source.py            — scan against baseline.
  review_input_keys_single_source.py --refresh  — rewrite the baseline.
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import ast
from pathlib import Path
from typing import Iterable

from internal_lints import LintFinding
from internal_lints import base as _base
from internal_lints._dispatch import rule_id_for
from internal_lints.base import LintSpec
from sdd_core import cli

_RULE_ID = rule_id_for(__name__, __file__)
_FORBIDDEN_LITERALS: frozenset[str] = frozenset({
    "tier2_scores",
    "documents_reviewed",
    "cross_validation",
    "testing_thoroughness",
    "final_scope_demotions_predicted",
})

# Allow-list — file-level only. Each entry names a canonical owner of
# the literals; new files added here recreate the duplication this lint
# closes. Directory-level tokens stay restricted to tests / migrations
# because those tracks are not part of the production contract.
#
# * ``sdd_core/review_input.py`` — canonical input contract owner.
# * ``sdd_core/review_quality_schema.py`` — envelope-side constants
#   shared with the input contract.
# * ``sdd_core/doc_config.py`` — mapping owner; references
#   ``testing_thoroughness`` from the supplemental layout.
# * ``review/update-quality.py`` — writer that consumes the input
#   contract. Surfaces the literals as the entry point for the script.
# * ``review/pipeline_phases/prompt_builder.py`` — renderer that emits
#   prose using the literals (re-exposed via review_input renderers).
# * ``review_quality/findings.py`` — owns the ``FindingSource`` literal
#   alias whose value happens to match the input key (semantically
#   distinct from the input contract — see the canonical-owner comment
#   inside the file).
# * ``internal_lints/review_input_keys_single_source.py`` — the lint
#   module itself stores the literals as data.
_ALLOWLIST_SUFFIXES: tuple[str, ...] = (
    "sdd_core/review_input.py",
    "sdd_core/review_quality_schema.py",
    "sdd_core/doc_config.py",
    "internal_lints/review_input_keys_single_source.py",
    "review/update-quality.py",
    "review/pipeline_phases/prompt_builder.py",
    "review_quality/findings.py",
)


def _is_allowed(path: Path) -> bool:
    posix = path.as_posix()
    if posix.startswith("tests/") or posix.startswith("migrations/"):
        return True
    if "/tests/" in posix or "/migrations/" in posix:
        return True
    return any(posix.endswith(suffix) for suffix in _ALLOWLIST_SUFFIXES)


class _StringLiteralChecker:
    """Flag ``ast.Constant`` nodes whose value is one of the five keys."""

    rule_id = _RULE_ID
    severity = "error"

    def check(self, node: ast.AST, path: Path) -> Iterable[LintFinding]:
        if _is_allowed(path):
            return ()
        if not isinstance(node, ast.Constant):
            return ()
        if not isinstance(node.value, str):
            return ()
        if node.value not in _FORBIDDEN_LITERALS:
            return ()
        return (LintFinding(
            rule_id=self.rule_id,
            severity=self.severity,
            file=str(path),
            line=getattr(node, "lineno", 1),
            message=(
                f"Inline {node.value!r} literal — the five top-level "
                "sub-agent input keys are owned by sdd_core.review_input "
                "and sdd_core.review_quality_schema. Import the "
                "constant or the TypedDict instead of duplicating the "
                "literal."
            ),
        ),)


SPEC = LintSpec(
    rule_id=_RULE_ID,
    roots=(".cursor/skills/sdd-common/scripts",),
    checkers=(_StringLiteralChecker(),),
)


analyze = SPEC.analyze
compare_baseline = SPEC.compare_baseline


def main() -> None:
    _base.run_lint_cli(SPEC)


if __name__ == "__main__":
    cli.run_main(main)
