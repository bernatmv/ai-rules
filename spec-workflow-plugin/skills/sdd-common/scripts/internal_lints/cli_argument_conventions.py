#!/usr/bin/env python3
"""Lint: forbid direct ``parser.add_argument("--feature"...)`` declarations.

Per W7 the canonical workflow-scoped selector is ``--target`` (registered
via :func:`sdd_core.cli.target_argument`). Direct ``parser.add_argument``
calls for ``--feature`` / ``--repo-id`` / ``--spec-name`` / ``--workspace``
in script bodies re-introduce the per-script flag drift the migration
removed.

The ``sdd_core.cli`` package itself still declares the legacy helpers
(``add_workspace_arg`` / ``add_feature_arg`` / etc.) for migration
ergonomics; the lint scope is everything *outside* ``sdd_core/cli/``.

Usage:
  cli_argument_conventions.py            — scan and diff against baseline.
  cli_argument_conventions.py --refresh  — rewrite the baseline.
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import ast
from pathlib import Path
from typing import Iterable

from internal_lints import LintFinding
from internal_lints import base as _base
from internal_lints._dispatch import rule_id_for
from internal_lints._legacy_flags import LEGACY_FLAG_NAMES, CARVE_OUTS
from internal_lints.base import LintSpec
from sdd_core import cli

_RULE_ID = rule_id_for(__name__, __file__)
_FORBIDDEN_FLAGS: frozenset[str] = LEGACY_FLAG_NAMES
_LEGACY_ALLOWLIST: dict[str, frozenset[str]] = CARVE_OUTS


def _path_allows_flag(path: Path, flag: str) -> bool:
    suffix = path.as_posix()
    for key, allowed in _LEGACY_ALLOWLIST.items():
        if suffix.endswith(key) and flag in allowed:
            return True
    return False


def _is_add_argument_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    return isinstance(func, ast.Attribute) and func.attr == "add_argument"


def _first_string_arg(node: ast.Call) -> "str | None":
    if not node.args:
        return None
    first = node.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value
    return None


class _AddArgumentChecker:
    """Flag forbidden ``parser.add_argument("--feature"...)`` calls."""

    rule_id = _RULE_ID
    severity = "error"

    def check(self, node: ast.AST, path: Path) -> Iterable[LintFinding]:
        if not _is_add_argument_call(node):
            return ()
        assert isinstance(node, ast.Call)  # narrowed by _is_add_argument_call
        flag = _first_string_arg(node)
        if flag is None or flag not in _FORBIDDEN_FLAGS:
            return ()
        if _path_allows_flag(path, flag):
            return ()
        return (LintFinding(
            rule_id=self.rule_id,
            severity=self.severity,
            file=str(path),
            line=getattr(node, "lineno", 1),
            message=(
                f"Direct `parser.add_argument({flag!r}, ...)` is forbidden "
                f"outside `sdd_core/cli/`. Use `cli.target_argument(parser, "
                f"family=\"workspace|spec|approval|discovery\")` to register "
                f"the canonical `--target` flag instead."
            ),
        ),)


SPEC = LintSpec(
    rule_id=_RULE_ID,
    roots=(
        ".cursor/skills/sdd-common/scripts/spec",
        ".cursor/skills/sdd-common/scripts/workspace",
        ".cursor/skills/sdd-common/scripts/approval",
        ".cursor/skills/sdd-common/scripts/discovery",
        ".cursor/skills/sdd-common/scripts/prd",
        ".cursor/skills/sdd-common/scripts/impl",
    ),
    checkers=(_AddArgumentChecker(),),
)


analyze = SPEC.analyze
compare_baseline = SPEC.compare_baseline


def main() -> None:
    _base.run_lint_cli(SPEC)


if __name__ == "__main__":
    cli.run_main(main)
