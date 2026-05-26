#!/usr/bin/env python3
"""Lint: forbid ``subprocess(..., shell=True)`` in skill scripts.

Delegates walk / parse / baseline / envelope to
:mod:`internal_lints.base`. The AST check is all this module owns.

Usage:
  no_shell_true.py            — scan and diff against baseline; fail on new findings.
  no_shell_true.py --refresh  — rewrite the baseline to match observed findings.

Exit codes: 0 when clean (or baseline refreshed), 1 on new/stale findings.
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
_SUBPROCESS_FUNCS = frozenset({"run", "Popen", "call", "check_call", "check_output"})



class ShellTrueChecker:
    """Flag ``subprocess.<func>(..., shell=True)`` and bare-name imports."""

    rule_id = _RULE_ID
    severity = "error"

    def check(self, node: ast.AST, path: Path) -> Iterable[LintFinding]:
        if not isinstance(node, ast.Call):
            return
        func = node.func
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            if func.value.id != "subprocess":
                return
        elif isinstance(func, ast.Name):
            if func.id not in _SUBPROCESS_FUNCS:
                return
        else:
            return
        for kw in node.keywords:
            if (
                kw.arg == "shell"
                and isinstance(kw.value, ast.Constant)
                and kw.value.value is True
            ):
                yield LintFinding(
                    rule_id=self.rule_id,
                    severity=self.severity,
                    file=str(path),
                    line=node.lineno,
                    message=(
                        "subprocess call uses shell=True — replace with "
                        "sdd_core.security.subprocess_safe.safe_run_test"
                    ),
                )
                return


SPEC = LintSpec(
    rule_id=_RULE_ID,
    roots=(".cursor/skills",),
    checkers=(ShellTrueChecker(),),
)


analyze = SPEC.analyze
compare_baseline = SPEC.compare_baseline


def scan_file(path: Path) -> list[LintFinding]:
    """Backward-compatible single-path scan used by older tests."""
    return _base.scan_file(Path(path), SPEC.checkers)


def main() -> None:
    _base.run_lint_cli(SPEC)


if __name__ == "__main__":
    cli.run_main(main)
