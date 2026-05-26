#!/usr/bin/env python3
"""Lint: forbid the legacy ``<repo>/.spec-workflow/.sdd-state/`` layout.

The two-tier state layout (see ``references/state-scope.md``) splits
state by purpose:

  - per-spec:  ``<repo>/.spec-workflow/specs/<spec>/.sdd-state/``
  - workspace: ``<coord>/.spec-workflow/workspace/<feature>/.sdd-state/``
  - standalone: ``<repo>/.spec-workflow/standalone/<spec>/.sdd-state/``

A literal ``".spec-workflow/.sdd-state"`` (or its joined-from-parts
equivalent ``".spec-workflow"`` + ``".sdd-state"`` adjacency) implies
the legacy single-tier shape. Every new write target must route
through :func:`sdd_core.workspace_state_loader.state_path` or
:func:`sdd_core.workspace_state_loader.resolve_state_dir` so adding a
new persisted file is one row in ``_FILENAME_PURPOSES`` rather than a
fresh inline literal.

Usage:
  workspace_state_layout.py            — scan and diff against baseline.
  workspace_state_layout.py --refresh  — rewrite the baseline.
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
_LEGACY_LITERAL = ".spec-workflow/.sdd-state"

# Allow-list — files that may legitimately carry the legacy literal:
# * The loader itself imports the constant.
# * The lint module stores the literal as data.
# * The dispatch row that registers this rule (description carries
#   the literal as guidance prose).
# * ``paths.py`` owns the legacy fallback consumers route through.
# Legacy consumers — entries shrink as each migrates onto the loader.
_ALLOWLIST_PATHS: tuple[tuple[str, ...], ...] = (
    ("sdd_core", "workspace_state_loader.py"),
    ("internal_lints", "workspace_state_layout.py"),
    ("internal_lints", "_dispatch.py"),
    ("sdd_core", "paths.py"),
    ("sdd_core", "harness", "loader.py"),
    ("sdd_core", "reference_acks.py"),
    ("sdd_core", "detect_doc_state_cache.py"),
    ("util", "probe-harness.py"),
)


def _is_allowed(path: Path) -> bool:
    parts = path.parts
    for suffix in _ALLOWLIST_PATHS:
        if len(parts) < len(suffix):
            continue
        if tuple(parts[-len(suffix):]) == suffix:
            return True
    return False


class _StringLiteralChecker:
    """Flag string literals that bake the legacy single-tier layout."""

    rule_id = _RULE_ID
    severity = "error"

    def check(self, node: ast.AST, path: Path) -> Iterable[LintFinding]:
        if _is_allowed(path):
            return ()
        if not isinstance(node, ast.Constant):
            return ()
        if not isinstance(node.value, str):
            return ()
        if _LEGACY_LITERAL not in node.value:
            return ()
        return (LintFinding(
            rule_id=self.rule_id,
            severity=self.severity,
            file=str(path),
            line=getattr(node, "lineno", 1),
            message=(
                "Inline '.spec-workflow/.sdd-state' literal — the "
                "two-tier state layout requires routing through "
                "sdd_core.workspace_state_loader.state_path() / "
                "resolve_state_dir() so a new file's tier (per-spec / "
                "workspace / standalone) is decided centrally rather "
                "than baked into the call site. See "
                "references/state-scope.md."
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
