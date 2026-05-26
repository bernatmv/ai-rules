#!/usr/bin/env python3
"""Lint: forbid bare ``[sys.executable, str(<script>.py), …]`` subprocess spawns.

Layer 2 of the invocation contract (`references/script-conventions.md`
§ Bootstrap Pattern) lives in
:func:`sdd_core.subprocess_dispatch.run_dispatched`. Every production
fan-out and test ride that helper; a direct
``[sys.executable, str(<concrete>.py), …]`` bypasses the dispatcher's
``--project`` pre-scan, audit hooks, and ``PYTHONDONTWRITEBYTECODE=1``
injection.

The lint flags any ``subprocess.run`` / ``subprocess.Popen`` /
``subprocess.call`` / ``subprocess.check_call`` /
``subprocess.check_output`` call whose first positional argument is a
list literal that contains both ``sys.executable`` (as ``Name`` ``"sys"``
attribute ``"executable"`` or as ``"sys.executable"`` attribute access)
and a ``str(...)`` call applied to a value whose name suggests a script
path. ``sdd_core/subprocess_dispatch.py`` is the canonical seam — it
is exempt.

Usage:
  no_bare_subprocess_dispatch.py            — scan and diff against baseline.
  no_bare_subprocess_dispatch.py --refresh  — rewrite the baseline.

Exit codes: 0 when clean, 1 on new/stale findings.
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
_SUBPROCESS_FUNCS = frozenset(
    {"run", "Popen", "call", "check_call", "check_output"}
)
_EXEMPT_BASENAMES = frozenset(
    {
        # The single-source helper itself — must shell out.
        "subprocess_dispatch.py",
        # Test helper that wraps the dispatcher.
        "sdd_shim.py",
        # Dispatcher's own module — entry point for the contract.
        "__main__.py",
    }
)


def _is_subprocess_call(func: ast.AST) -> bool:
    """Return True for any ``subprocess.<spawn>`` or ``subprocess(...)`` call."""
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        return func.value.id == "subprocess" and func.attr in _SUBPROCESS_FUNCS
    if isinstance(func, ast.Name):
        # `from subprocess import run` style — bare names.
        return func.id in _SUBPROCESS_FUNCS
    return False


def _is_sys_executable(node: ast.AST) -> bool:
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return node.value.id == "sys" and node.attr == "executable"
    return False


def _is_str_call_on_path(node: ast.AST) -> bool:
    """True for ``str(<expr>)`` where the expr looks path-shaped.

    Path-shaped means one of:
      * ``ast.Name`` ending in ``_path`` / ``_PATH`` / ``_SCRIPT`` /
        ``script_path`` / ``_dir / "<name>.py"`` etc.
      * ``ast.BinOp`` with `/` (path concatenation).
      * Any other ``Attribute`` access that resolves at call time
        (we accept any ``str(<x>)`` because catching false negatives
        is more important than rejecting borderline shapes here).
    """
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Name) and func.id == "str":
        return True
    return False


class BareSubprocessDispatchChecker:
    """Flag ``subprocess.run([sys.executable, str(...py), ...])``."""

    rule_id = _RULE_ID
    severity = "error"

    def check(self, node: ast.AST, path: Path) -> Iterable[LintFinding]:
        if path.name in _EXEMPT_BASENAMES:
            return
        if not isinstance(node, ast.Call):
            return
        if not _is_subprocess_call(node.func):
            return
        if not node.args:
            return
        first = node.args[0]
        if not isinstance(first, (ast.List, ast.Tuple)):
            return
        # Detect ``[sys.executable, str(<script_path>), ...]``.
        elts = first.elts
        if not elts:
            return
        if not _is_sys_executable(elts[0]):
            return
        # If any subsequent element is the literal string "-m" then
        # the call is the dispatcher form (e.g. inside the helper or
        # the test runner) and is fine.
        for elt in elts[1:]:
            if isinstance(elt, ast.Constant) and elt.value == "-m":
                return
            if _is_str_call_on_path(elt):
                yield LintFinding(
                    rule_id=self.rule_id,
                    severity=self.severity,
                    file=str(path),
                    line=node.lineno,
                    message=(
                        "Direct [sys.executable, str(<script>.py), …] bypasses "
                        "the dispatcher contract. Replace with "
                        "sdd_core.subprocess_dispatch.run_dispatched(...) "
                        "(production) or tests/_helpers/sdd_shim.run_sdd(...) "
                        "(tests). See references/script-conventions.md "
                        "§ Bootstrap Pattern."
                    ),
                )
                return


SPEC = LintSpec(
    rule_id=_RULE_ID,
    roots=(".cursor/skills", "tests"),
    checkers=(BareSubprocessDispatchChecker(),),
)


analyze = SPEC.analyze
compare_baseline = SPEC.compare_baseline


def main() -> None:
    _base.run_lint_cli(SPEC)


if __name__ == "__main__":
    cli.run_main(main)
