#!/usr/bin/env python3
"""Lint: forbid reintroducing the legacy ``validate-*.py`` shim names.

Per the verb migration (W5), per-document checks ship as ``lint-*.py``
and cross-doc checks as ``check-*.py``. ``validate`` is reserved for
schema / shape checks on a structured artifact (e.g.
``review-quality.json``). Reintroducing a ``validate-`` shape under
``spec/`` or ``workspace/`` would re-introduce verb-vocabulary drift.

The lint scans the file inventory under
``.cursor/skills/sdd-common/scripts/{spec,workspace}/`` for any path
matching the forbidden shape and emits a finding.

Usage:
  no_validate_for_lint.py            — scan and diff against baseline.
  no_validate_for_lint.py --refresh  — rewrite the baseline.
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import re
from pathlib import Path
from typing import Iterable

from internal_lints import LintFinding
from internal_lints import base as _base
from internal_lints._dispatch import rule_id_for
from internal_lints.base import LintSpec
from sdd_core import cli

_RULE_ID = rule_id_for(__name__, __file__)
_FORBIDDEN_SHAPES: tuple[re.Pattern[str], ...] = (
    re.compile(r"spec/validate-(requirements|tasks|traceability)\.py$"),
    re.compile(r"workspace/validate-(spec)\.py$"),
)


class _PathChecker:
    """Filename-pattern checker — runs once per .py file under the roots."""

    rule_id = _RULE_ID
    severity = "error"

    def check_path(self, path: Path) -> Iterable[LintFinding]:
        rel = path.as_posix()
        for shape in _FORBIDDEN_SHAPES:
            if shape.search(rel):
                return (LintFinding(
                    rule_id=self.rule_id,
                    severity=self.severity,
                    file=str(path),
                    line=1,
                    message=(
                        "Filename uses the legacy `validate-*.py` "
                        "verb. Per W5, rename to `lint-*.py` "
                        "(per-doc) or `check-*.py` (cross-doc). "
                        "`validate` is reserved for schema checks "
                        "on structured artifacts."
                    ),
                ),)
        return ()


SPEC = LintSpec(
    rule_id=_RULE_ID,
    roots=(
        ".cursor/skills/sdd-common/scripts/spec",
        ".cursor/skills/sdd-common/scripts/workspace",
    ),
    path_checkers=(_PathChecker(),),
)


analyze = SPEC.analyze
compare_baseline = SPEC.compare_baseline


def main() -> None:
    _base.run_lint_cli(SPEC)


if __name__ == "__main__":
    cli.run_main(main)
