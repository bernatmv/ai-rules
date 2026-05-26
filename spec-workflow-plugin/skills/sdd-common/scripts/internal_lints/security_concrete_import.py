#!/usr/bin/env python3
"""Lint: forbid concrete imports of security primitives outside the package.

Direct imports like ``from sdd_core.security.state import
TransactionalStore`` defeat the pluggable-seam contract — auditors who
swap the lock or runner allowlist via factory cannot dislodge a hard
dependency on the bundled implementation. Callers must consume
``sdd_core.security.locked_store`` / ``default_allowlist`` instead.

Ships in **detect-only** mode with a populated baseline; flips to
**enforce** once the baseline shrinks to empty.

Usage:
  security_concrete_import.py            — scan and diff baseline.
  security_concrete_import.py --refresh  — rewrite baseline.
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import ast
from pathlib import Path
from typing import Iterable

from internal_lints import LintFinding
from internal_lints import base as _base
from internal_lints.base import LintSpec
from sdd_core import cli

from internal_lints._dispatch import rule_id_for

_RULE_ID = rule_id_for(__name__, __file__)

_FORBIDDEN_MODULES = frozenset({
    "sdd_core.security.state",
    "sdd_core.security.subprocess_safe",
})

_PACKAGE_PARTS = ("sdd_core", "security")


def _is_inside_security_package(path: Path) -> bool:
    parts = path.parts
    for idx in range(len(parts) - 1):
        if parts[idx] == _PACKAGE_PARTS[0] and parts[idx + 1] == _PACKAGE_PARTS[1]:
            return True
    return False


class ConcreteImportChecker:
    """Flag ``from sdd_core.security.{state,subprocess_safe} import …``."""

    rule_id = _RULE_ID
    severity = "warning"

    def check(self, node: ast.AST, path: Path) -> Iterable[LintFinding]:
        if _is_inside_security_package(path):
            return
        if not isinstance(node, ast.ImportFrom):
            return
        module = node.module or ""
        if module not in _FORBIDDEN_MODULES:
            return
        names = ", ".join(alias.name for alias in node.names)
        yield LintFinding(
            rule_id=self.rule_id,
            severity=self.severity,
            file=str(path),
            line=node.lineno,
            message=(
                f"concrete import 'from {module} import {names}' — use the "
                f"sdd_core.security accessor (locked_store / default_allowlist)"
            ),
        )


SPEC = LintSpec(
    rule_id=_RULE_ID,
    roots=(".cursor/skills",),
    checkers=(ConcreteImportChecker(),),
)


analyze = SPEC.analyze
compare_baseline = SPEC.compare_baseline


def main() -> None:
    _base.run_lint_cli(SPEC)


if __name__ == "__main__":
    cli.run_main(main)
