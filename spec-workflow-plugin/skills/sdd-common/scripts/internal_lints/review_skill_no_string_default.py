#!/usr/bin/env python3
"""Lint: forbid ``dict.get("review_skill", <non-None default>)``.

The default-value pattern is the recurrence vector for skill-name
drift: a fallback string default leaks the wrong skill name when the
gate session lacks ``review_skill``. The structural fix is to use
category-aware resolution (``ReviewSkill.for_category(category)``)
at the call site instead of a constant default. This lint blocks the
bad shape.

Allowed:
  cached.get("review_skill")
  cached.get("review_skill", None)

Forbidden:
  cached.get("review_skill", DEFAULT_REVIEW_SKILL)
  cached.get("review_skill", "sdd-review-spec-docs")
  cached.get("review_skill", some_string)

Usage:
  review_skill_no_string_default.py            — scan and diff against baseline.
  review_skill_no_string_default.py --refresh  — rewrite the baseline.
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
_KEY = "review_skill"

# Allow the lint to run on `review_skills.py` and itself.
_ALLOWLIST_SUFFIXES: tuple[str, ...] = (
    "sdd_core/review_skills.py",
    "internal_lints/review_skill_no_string_default.py",
)


def _is_allowed(path: Path) -> bool:
    posix = path.as_posix()
    return any(posix.endswith(suffix) for suffix in _ALLOWLIST_SUFFIXES)


def _is_review_skill_key(arg: ast.expr) -> bool:
    return (
        isinstance(arg, ast.Constant)
        and isinstance(arg.value, str)
        and arg.value == _KEY
    )


def _default_is_none(default: ast.expr) -> bool:
    """``None`` literal (only allowed default)."""
    return isinstance(default, ast.Constant) and default.value is None


class _ReviewSkillGetChecker:
    """Flag ``<expr>.get("review_skill", <non-None-default>)`` calls."""

    rule_id = _RULE_ID
    severity = "error"

    def check(self, node: ast.AST, path: Path) -> Iterable[LintFinding]:
        if _is_allowed(path):
            return ()
        if not isinstance(node, ast.Call):
            return ()
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "get"):
            return ()
        if len(node.args) < 2:
            return ()
        key, default = node.args[0], node.args[1]
        if not _is_review_skill_key(key):
            return ()
        if _default_is_none(default):
            return ()
        return (LintFinding(
            rule_id=self.rule_id,
            severity=self.severity,
            file=str(path),
            line=getattr(node, "lineno", 1),
            message=(
                "dict.get('review_skill', <default>) with a non-None "
                "default — the fallback-string pattern is forbidden "
                "because it poisons category-aware skill resolution. "
                "Use `cached.get('review_skill') or "
                "ReviewSkill.for_category(category)` so the resolved "
                "skill always matches the category."
            ),
        ),)


SPEC = LintSpec(
    rule_id=_RULE_ID,
    roots=(".cursor/skills/sdd-common/scripts",),
    checkers=(_ReviewSkillGetChecker(),),
)


analyze = SPEC.analyze
compare_baseline = SPEC.compare_baseline


def main() -> None:
    _base.run_lint_cli(SPEC)


if __name__ == "__main__":
    cli.run_main(main)
