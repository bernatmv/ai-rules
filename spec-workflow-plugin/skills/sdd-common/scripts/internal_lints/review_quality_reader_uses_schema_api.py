#!/usr/bin/env python3
"""Lint: forbid raw ``data.get("overall_score" | "documents" | "issues")``.

Readers under ``review/pipeline_phases/`` must consume the schema API
(:func:`sdd_core.review_quality_schema.get_active`,
:func:`get_by_scope`) rather than reaching into raw artifact dicts.
Direct ``data.get(...)`` calls reintroduce the writer/reader split that
the schema API closes.

The lint scopes to ``review/pipeline_phases/`` and only fires when the
receiver is a bare ``Name`` whose identifier is ``data`` (or a small set
of similar locals). Chained accesses such as ``rq.get_active(data).get(...)``
already route through the schema API and are accepted.

Usage:
  review_quality_reader_uses_schema_api.py            — scan against baseline.
  review_quality_reader_uses_schema_api.py --refresh  — rewrite the baseline.
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
_FORBIDDEN_KEYS: frozenset[str] = frozenset(
    {"overall_score", "documents", "issues", "by_scope"}
)
# Receiver names that indicate a raw artifact dict at the call site.
# A one-line variable rename anywhere should not silently bypass the
# lint — every common alias for a review-quality envelope is captured.
_RAW_RECEIVER_NAMES: frozenset[str] = frozenset({
    "data", "quality_data", "artifact_data", "quality_payload",
    "envelope", "artifact",
})

# Scope of the lint — only the readers under pipeline_phases/.
_SCOPED_DIR = "review/pipeline_phases/"

_ALLOWLIST_SUFFIXES: tuple[str, ...] = (
    "internal_lints/review_quality_reader_uses_schema_api.py",
)


def _in_scope(path: Path) -> bool:
    return _SCOPED_DIR in path.as_posix()


def _is_allowed(path: Path) -> bool:
    posix = path.as_posix()
    return any(posix.endswith(suffix) for suffix in _ALLOWLIST_SUFFIXES)


def _first_str_arg(node: ast.Call) -> "str | None":
    if not node.args:
        return None
    first = node.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value
    return None


class _RawDataGetChecker:
    """Flag ``data.get("overall_score"|"documents"|"issues")`` calls."""

    rule_id = _RULE_ID
    severity = "error"

    def check(self, node: ast.AST, path: Path) -> Iterable[LintFinding]:
        if _is_allowed(path) or not _in_scope(path):
            return ()
        if not isinstance(node, ast.Call):
            return ()
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != "get":
            return ()
        receiver = func.value
        if not isinstance(receiver, ast.Name):
            return ()
        if receiver.id not in _RAW_RECEIVER_NAMES:
            return ()
        key = _first_str_arg(node)
        if key is None or key not in _FORBIDDEN_KEYS:
            return ()
        return (LintFinding(
            rule_id=self.rule_id,
            severity=self.severity,
            file=str(path),
            line=getattr(node, "lineno", 1),
            message=(
                f"Raw {receiver.id}.get({key!r}, ...) — readers under "
                "review/pipeline_phases/ must consume the schema API "
                "(rq_schema.get_active(data) / get_by_scope(...)) so "
                "writer/reader drift cannot re-open."
            ),
        ),)


SPEC = LintSpec(
    rule_id=_RULE_ID,
    roots=(".cursor/skills/sdd-common/scripts/review/pipeline_phases",),
    checkers=(_RawDataGetChecker(),),
)


analyze = SPEC.analyze
compare_baseline = SPEC.compare_baseline


def main() -> None:
    _base.run_lint_cli(SPEC)


if __name__ == "__main__":
    cli.run_main(main)
