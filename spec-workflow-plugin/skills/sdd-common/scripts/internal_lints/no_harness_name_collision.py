#!/usr/bin/env python3
"""Lint: forbid advisory codes / messages that collide with harness names.

Advisory ``code`` and ``message`` are operator-facing strings — the
agent reads them to route remediation. When the copy substring-matches
a harness name (``cursor``, ``claude-code-standard``, etc.), the agent
can mis-classify the advisory as harness-scoped diagnostic rather than
the workflow-position signal it really is. The lint keeps copy
unambiguous regardless of which harness reads the envelope.

Heuristic: an advisory dict literal whose ``code`` or ``message``
substring contains a registered harness name is flagged. Subword-aware
matching keeps "cursor_advanced" out of the inventory while leaving
genuine references like "cursor.position" untouched (none exist
today; the lint guards future regressions cheaply).

Usage:
  no_harness_name_collision.py            — scan and diff against baseline.
  no_harness_name_collision.py --refresh  — rewrite the baseline.
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import ast
import re
from pathlib import Path
from typing import Iterable

from internal_lints import LintFinding
from internal_lints import base as _base
from internal_lints._dispatch import rule_id_for
from internal_lints.base import LintSpec
from sdd_core import cli

_RULE_ID = rule_id_for(__name__, __file__)


def _harness_names() -> tuple[str, ...]:
    """Return the registered harness names — empty tuple on import failure.

    The lint degrades to a no-op rather than crashing if the registry
    cannot be imported (e.g. partial package layout in CI). The caller
    sees an empty inventory and the checker yields no findings.
    """
    try:
        from sdd_core.harness.registry import available_adapter_names

        return tuple(available_adapter_names())
    except Exception:
        return ()


def _string_field(node: ast.Dict, field: str) -> "str | None":
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


def _is_advisory_dict(node: ast.Dict) -> bool:
    """Return True when the dict has the advisory-shape key set."""
    keys: set[str] = set()
    for key in node.keys:
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            keys.add(key.value)
    return "code" in keys or "level" in keys and "message" in keys


def _matches_harness(text: str, harness_names: Iterable[str]) -> "str | None":
    """Return the harness name that substring-matches *text*, or None."""
    if not text:
        return None
    lowered = text.lower()
    for name in harness_names:
        # Token-aware match — split harness name on punctuation and
        # require every token to appear in the text. ``cursor`` matches
        # ``cursor_advanced``; ``claude-code-standard`` requires every
        # segment to appear.
        tokens = [t for t in re.split(r"[-_.]", name.lower()) if t]
        if not tokens:
            continue
        if all(t in lowered for t in tokens):
            return name
    return None


class HarnessNameCollisionChecker:
    """Flag advisory dicts whose code/message references a harness name."""

    rule_id = _RULE_ID
    severity = "error"

    def __init__(self) -> None:
        self._harness_names = _harness_names()

    def check(self, node: ast.AST, path: Path) -> Iterable[LintFinding]:
        if not self._harness_names:
            return ()
        if not isinstance(node, ast.Dict) or not _is_advisory_dict(node):
            return ()
        for field in ("code", "message"):
            text = _string_field(node, field)
            if not text:
                continue
            collision = _matches_harness(text, self._harness_names)
            if collision is None:
                continue
            return (LintFinding(
                rule_id=self.rule_id,
                severity=self.severity,
                file=str(path),
                line=getattr(node, "lineno", 1),
                message=(
                    f"advisory {field}={text!r} collides with harness "
                    f"name {collision!r}. Rename the advisory copy so "
                    "operators reading the envelope don't mistake the "
                    "workflow-position signal for a harness diagnostic."
                ),
            ),)
        return ()


SPEC = LintSpec(
    rule_id=_RULE_ID,
    roots=(".cursor/skills",),
    checkers=(HarnessNameCollisionChecker(),),
)


analyze = SPEC.analyze
compare_baseline = SPEC.compare_baseline


def main() -> None:
    _base.run_lint_cli(SPEC)


if __name__ == "__main__":
    cli.run_main(main)
