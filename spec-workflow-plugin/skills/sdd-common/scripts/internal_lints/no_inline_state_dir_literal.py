#!/usr/bin/env python3
"""Lint: forbid inline ``".sdd-state"`` literals outside ``paths.py``.

The canonical owner of the ``.sdd-state`` directory name is
:data:`sdd_core.paths.STATE_DIR_NAME`. Every other site that needs the
literal must import the constant or compose through
:func:`sdd_core.paths.workflow_state_path` /
:func:`sdd_core.paths.state_dir`. Inline literals re-introduce the
"two truth sources" failure mode flagged in the
``pti-provisioning-phase-4`` consolidated fix plan (Workstream J).

Usage:
  no_inline_state_dir_literal.py            — scan and diff against baseline.
  no_inline_state_dir_literal.py --refresh  — rewrite the baseline.
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
_FORBIDDEN_LITERAL = ".sdd-state"

# Allow-list — files that may legitimately carry the literal:
# * ``paths.py`` is the single owner.
# * The lint module itself stores the literal as data.
# * Test fixtures and assets that exercise the literal directly.
_ALLOWLIST_SUFFIXES: tuple[str, ...] = (
    "sdd_core/paths.py",
    "internal_lints/no_inline_state_dir_literal.py",
)


def _is_allowed(path: Path) -> bool:
    posix = path.as_posix()
    return any(posix.endswith(suffix) for suffix in _ALLOWLIST_SUFFIXES)


class _StringLiteralChecker:
    """Flag ``ast.Constant`` nodes whose value is the forbidden literal."""

    rule_id = _RULE_ID
    severity = "error"

    def check(self, node: ast.AST, path: Path) -> Iterable[LintFinding]:
        if _is_allowed(path):
            return ()
        if not isinstance(node, ast.Constant):
            return ()
        if node.value != _FORBIDDEN_LITERAL:
            return ()
        return (LintFinding(
            rule_id=self.rule_id,
            severity=self.severity,
            file=str(path),
            line=getattr(node, "lineno", 1),
            message=(
                "Inline '.sdd-state' literal — route through "
                "sdd_core.paths.STATE_DIR_NAME or "
                "sdd_core.paths.workflow_state_path() / "
                "sdd_core.paths.state_dir() instead. The path constant "
                "owns one source of truth (see "
                "references/state-scope.md)."
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
