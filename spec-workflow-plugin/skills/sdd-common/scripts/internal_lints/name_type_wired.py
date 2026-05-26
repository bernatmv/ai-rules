#!/usr/bin/env python3
"""Lint: every identifier-flag declaration uses ``cli.name_type(...)``.

Usage:
  name_type_wired.py            — scan and diff against baseline; fail on new findings.
  name_type_wired.py --refresh  — rewrite the baseline to observed findings.

Flags whose first positional matches one of the well-known identifier
names (``--spec-name``, ``--target-name``, ``--category-name``,
``--feature``, ``--repo-id``, ``--approval-id``, ``--log-id``) MUST
declare ``type=cli.name_type(<kind>)`` so argparse rejects malformed
identifiers before the script body runs (H6 — path-traversal defence).

The lint walks every ``parser.add_argument`` AST call under
``.cursor/skills/`` and flags any identifier flag whose keyword
arguments do not include a ``type=...name_type...`` callable.
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

# First-positional flag names that MUST carry ``name_type``.
_IDENTIFIER_FLAGS = frozenset({
    "--spec-name",
    "--target-name",
    "--category-name",
    "--feature",
    "--repo-id",
    "--approval-id",
    "--log-id",
})


def _is_add_argument(call: ast.Call) -> bool:
    """Match ``<obj>.add_argument(...)`` AST shape only."""
    func = call.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr == "add_argument"
    )


def _first_positional_string(call: ast.Call) -> "str | None":
    if not call.args:
        return None
    first = call.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value
    return None


def _has_name_type_keyword(call: ast.Call) -> bool:
    for kw in call.keywords:
        if kw.arg != "type":
            continue
        # Match ``cli.name_type(...)`` or ``name_type(...)`` calls.
        value = kw.value
        if isinstance(value, ast.Call):
            target = value.func
            if isinstance(target, ast.Attribute) and target.attr == "name_type":
                return True
            if isinstance(target, ast.Name) and target.id == "name_type":
                return True
    return False


class NameTypeChecker:
    """Flag identifier ``add_argument`` calls missing ``name_type``."""

    rule_id = _RULE_ID
    severity = "error"

    def check(self, node: ast.AST, path: Path) -> Iterable[LintFinding]:
        if not isinstance(node, ast.Call) or not _is_add_argument(node):
            return
        flag = _first_positional_string(node)
        if flag is None or flag not in _IDENTIFIER_FLAGS:
            return
        if _has_name_type_keyword(node):
            return
        yield LintFinding(
            rule_id=self.rule_id,
            severity=self.severity,
            file=str(path),
            line=node.lineno,
            message=(
                f"identifier flag {flag!r} missing "
                f"type=cli.name_type(...) — wire validate_name "
                "via the factory so argparse rejects malformed names "
                "before the script body runs."
            ),
        )


SPEC = LintSpec(
    rule_id=_RULE_ID,
    roots=(".cursor/skills",),
    checkers=(NameTypeChecker(),),
)


analyze = SPEC.analyze
compare_baseline = SPEC.compare_baseline


def main() -> None:
    _base.run_lint_cli(SPEC)


if __name__ == "__main__":
    cli.run_main(main)
