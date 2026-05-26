#!/usr/bin/env python3
"""Lint: every workspace shim must declare ``__sdd_context_needs__``.

V-7 wires :class:`sdd_core.context.WorkflowContext` resolution through a
module-level constant that mirrors the workflow graph's
``context_needs``. The constant lets the ``with_context`` resolver chain
and the ``cli.resolve_context`` helper agree on which fields the shim
consumes; without it a script silently re-types values the system
already knows.

Scope: the lint only inspects ``workspace/*.py`` shims (the executable
entry points). Library helpers under ``sdd_core/``, the registry
loaders under ``internal_lints/``, the ``__init__.py`` and
``_bootstrap.py`` plumbing files, and any module without a top-level
``def main()`` are exempt — those are not user-facing shims.

Usage:
  with_context_coverage.py            — scan and diff against baseline.
  with_context_coverage.py --refresh  — rewrite the baseline.
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

# Files that ship without a ``main`` entry point — plumbing, fixtures,
# package marker. Skipping these by name (rather than by AST inspection)
# is cheaper and keeps the exemption list grep-able.
_NON_SHIM_FILES: frozenset[str] = frozenset({
    "__init__.py", "_bootstrap.py",
})


def _module_declares_context_needs(tree: ast.Module) -> bool:
    """True when the module sets ``__sdd_context_needs__`` at top level."""
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id == "__sdd_context_needs__"
                ):
                    return True
        elif isinstance(node, ast.AnnAssign):
            if (
                isinstance(node.target, ast.Name)
                and node.target.id == "__sdd_context_needs__"
            ):
                return True
    return False


def _module_defines_main(tree: ast.Module) -> bool:
    """True when the module defines a top-level ``main`` callable."""
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == "main":
                return True
    return False


class _CoverageChecker:
    """Module-level NodeChecker — fires once per file (on the Module node).

    Reports shims with ``def main()`` but no ``__sdd_context_needs__``
    constant. Using ``ast.Module`` as the trigger means the framework's
    per-node walk visits exactly once per file, so the per-file work
    happens once per ``ast.walk`` pass without manual book-keeping.
    """

    rule_id = _RULE_ID
    severity = "error"

    def check(self, node: ast.AST, path: Path) -> Iterable[LintFinding]:
        if not isinstance(node, ast.Module):
            return ()
        if path.name in _NON_SHIM_FILES:
            return ()
        if not _module_defines_main(node):
            return ()
        if _module_declares_context_needs(node):
            return ()
        return (LintFinding(
            rule_id=self.rule_id,
            severity=self.severity,
            file=str(path),
            line=1,
            message=(
                f"{path.name} has `def main()` but no `__sdd_context_needs__`"
                f" tuple at module scope. Declare the workflow-graph "
                f"`context_needs` mirror so the resolver chain knows "
                f"which fields the shim consumes (V-7)."
            ),
        ),)


SPEC = LintSpec(
    rule_id=_RULE_ID,
    roots=(
        ".cursor/skills/sdd-common/scripts/workspace",
        ".cursor/skills/sdd-common/scripts/spec",
        ".cursor/skills/sdd-common/scripts/discovery",
        ".cursor/skills/sdd-common/scripts/prd",
    ),
    checkers=(_CoverageChecker(),),
)


analyze = SPEC.analyze
compare_baseline = SPEC.compare_baseline


def main() -> None:
    _base.run_lint_cli(SPEC)


if __name__ == "__main__":
    cli.run_main(main)
