#!/usr/bin/env python3
"""Lint: forbid bare ``"review/update-quality.py"`` literals outside the builder.

The canonical owner of the invocation literal is
:func:`sdd_core.command_templates.build_update_quality_command` and its
peer :func:`build_review_update_quality_command`. Every other site that
wants the script path must consume the builder, the
:data:`UPDATE_QUALITY_SCRIPT` constant, or the script's argparse output.
Re-introducing the bare literal in ``launch/prompt.py`` (or any other
caller) recreates the cross-module-contract drift the builder collapses.

Usage:
  update_quality_command_uses_builder.py            — scan against baseline.
  update_quality_command_uses_builder.py --refresh  — rewrite the baseline.
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
_FORBIDDEN_LITERAL = "review/update-quality.py"

# Allow-list — files that may legitimately carry the bare literal:
# * ``sdd_core/command_templates.py`` is the single owner.
# * ``internal_lints/_dispatch.py`` describes the literal in the lint's
#   own remediation text.
# * The lint module itself stores the literal as data.
# * The script's own argparse / docstring self-references.
# * ``pipeline_phases/templates.py`` mentions the literal in
#   descriptive boundary prose (no flag emission), not as a runnable
#   command.
# * ``workspace/ensure-healthy.py`` uses the literal as a shim path
#   constant routed through the canonical ``build_review_update_quality_command``
#   builder; the surrounding mentions are docstring / help-text prose.
# * ``sdd_core/workspace_health_checks.py`` mentions the literal in
#   advisory detail strings shown to operators (descriptive prose).
# * Tests under ``tests/``.
_ALLOWLIST_SUFFIXES: tuple[str, ...] = (
    "sdd_core/command_templates.py",
    "internal_lints/_dispatch.py",
    "internal_lints/update_quality_command_uses_builder.py",
    "internal_lints/review_input_keys_single_source.py",
    "review/update-quality.py",
    "review/pipeline_phases/templates.py",
    "workspace/ensure-healthy.py",
    "sdd_core/workspace_health_checks.py",
)


def _is_allowed(path: Path) -> bool:
    posix = path.as_posix()
    if "/tests/" in posix or posix.startswith("tests/"):
        return True
    return any(posix.endswith(suffix) for suffix in _ALLOWLIST_SUFFIXES)


class _StringLiteralChecker:
    """Flag ``ast.Constant`` nodes whose value is the bare invocation literal."""

    rule_id = _RULE_ID
    severity = "error"

    def check(self, node: ast.AST, path: Path) -> Iterable[LintFinding]:
        if _is_allowed(path):
            return ()
        if not isinstance(node, ast.Constant):
            return ()
        if not isinstance(node.value, str):
            return ()
        if _FORBIDDEN_LITERAL not in node.value:
            return ()
        return (LintFinding(
            rule_id=self.rule_id,
            severity=self.severity,
            file=str(path),
            line=getattr(node, "lineno", 1),
            message=(
                "Inline 'review/update-quality.py' literal — route through "
                "sdd_core.command_templates.build_update_quality_command(...) "
                "or build_review_update_quality_command(...) instead. The "
                "builder owns one source of truth for the sub-agent "
                "invocation."
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
