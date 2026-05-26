#!/usr/bin/env python3
"""Lint: data-driven advisory placement.

Each entry under ``workflow-graph.json::advisories`` declares where an
advisory fires and where the workflow naturally refreshes the underlying
state. The lint asserts that every advisory whose ``name`` is registered
in the graph also matches the declared ``severity_when_phase_mismatch``
in code — drift between the two is the recurrence vector for advisories
firing at the wrong phase or with the wrong severity.

The graph is the single source of truth: adding an advisory or changing
its placement is a one-row JSON edit, and this lint reflects on the
graph at runtime so new advisories are auto-covered.

Usage:
  advisory_phase_placement.py            — scan and diff against baseline.
  advisory_phase_placement.py --refresh  — rewrite the baseline.
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
from sdd_core import cli, paths, workflow_graph

_RULE_ID = rule_id_for(__name__, __file__)


def _advisory_placements() -> "dict[str, workflow_graph.AdvisoryPlacement]":
    try:
        return workflow_graph.advisory_placements()
    except Exception:
        return {}


def _string_field(node: ast.Dict, field: str) -> "str | None":
    """Return the string literal value of *field* in dict *node*, if any."""
    for key, value in zip(node.keys, node.values):
        if (
            isinstance(key, ast.Constant)
            and isinstance(key.value, str)
            and key.value == field
            and isinstance(value, ast.Constant)
            and isinstance(value.value, str)
        ):
            return value.value
    return None


class _AdvisoryDictChecker:
    """Flag advisory dicts whose ``name`` + ``status`` drift from the graph."""

    rule_id = _RULE_ID
    severity = "error"

    def __init__(self) -> None:
        self._placements = _advisory_placements()

    def check(self, node: ast.AST, path: Path) -> Iterable[LintFinding]:
        if not self._placements:
            return ()
        # Only inspect Return statements wrapping a literal dict — the
        # advisory contract is explicit ``return {"name": ..., ...}``.
        if not isinstance(node, ast.Return):
            return ()
        value = node.value
        if not isinstance(value, ast.Dict):
            return ()
        name = _string_field(value, "name")
        if name is None or name not in self._placements:
            return ()
        placement = self._placements[name]
        status = _string_field(value, "status")
        if status is None:
            return ()  # `pass` returns are wrapped elsewhere — skip.
        if status == "pass":
            return ()  # advisory not firing — no severity to check.
        expected = placement.severity_when_phase_mismatch
        if status == expected:
            return ()
        return (LintFinding(
            rule_id=self.rule_id,
            severity=self.severity,
            file=str(path),
            line=getattr(node, "lineno", 1),
            message=(
                f"advisory {name!r} returns status={status!r} but "
                f"workflow-graph.json declares "
                f"severity_when_phase_mismatch={expected!r}. Update the "
                f"graph or the advisory so the two agree — drift breaks "
                f"the placement contract."
            ),
        ),)


def _scripts_root() -> str:
    """Return the repo-relative scripts root that hosts the advisories."""
    try:
        root = paths.find_skills_root()
        scripts = paths.common_scripts_dir(root)
        repo = paths.find_workflow_root()
        return str(scripts.relative_to(repo))
    except Exception:
        return ".cursor/skills/sdd-common/scripts"


SPEC = LintSpec(
    rule_id=_RULE_ID,
    roots=(_scripts_root(),),
    checkers=(_AdvisoryDictChecker(),),
)


analyze = SPEC.analyze
compare_baseline = SPEC.compare_baseline


def main() -> None:
    _base.run_lint_cli(SPEC)


if __name__ == "__main__":
    cli.run_main(main)
