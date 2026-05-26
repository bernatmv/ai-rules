#!/usr/bin/env python3
"""Lint: SKILL.md best-practice size + disclosure invariants.

Two checks per SKILL.md body:

1. **Size budget** — body ≤ 500 lines (Anthropic § *Token budgets*).
2. **Mirrored heading** — no SKILL.md re-prints a section heading
   already owned by a ``references/*.md`` peer (today: ``## Approval
   Flow``, ``## Prompt Conventions``). The canonical doc owns the
   prose; SKILL bodies link to it (Anthropic § *Progressive disclosure*).

Detect-only at landing — populated baseline grandfather-clauses any
SKILL that already violates either check; CI flips to enforce one
milestone later. Refresh the baseline with ``--refresh``.

Usage:
  skill_md_size_and_disclosure.py            — scan every SKILL.md, fail on new findings.
  skill_md_size_and_disclosure.py --refresh  — rewrite the baseline to observed findings.
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import re
from pathlib import Path
from typing import Iterable

from internal_lints import LintFinding
from internal_lints import base as _base
from internal_lints.base import LintSpec
from sdd_core import cli

from internal_lints._dispatch import rule_id_for

_RULE_ID = rule_id_for(__name__, __file__)
_MAX_LINES = 500
# Headings whose body lives in a sibling ``references/*.md``. Adding a
# row here adds one disclosure invariant for every SKILL.md.
_MIRRORED_HEADINGS = (
    re.compile(r"^##\s+Approval Flow\s*$", re.IGNORECASE),
    re.compile(r"^##\s+Prompt Conventions\s*$", re.IGNORECASE),
)


class SizeAndDisclosureChecker:
    """File-level size budget + per-line mirrored-heading check."""

    rule_id = _RULE_ID
    severity = "warning"

    def __init__(self) -> None:
        self._reported_size: dict[Path, bool] = {}
        self._oversize_line_count: dict[Path, int] = {}

    def prepare(self, path: Path, text: str) -> None:
        # Reset per-file dedup so re-running across multiple files in
        # one process does not double-flag.
        self._reported_size[path] = False
        line_count = text.count("\n") + (0 if text.endswith("\n") else 1)
        if line_count > _MAX_LINES:
            self._reported_size[path] = True
            self._oversize_line_count[path] = line_count

    def check_line(
        self, line: str, lineno: int, path: Path,
    ) -> Iterable[LintFinding]:
        if lineno == 1 and self._reported_size.get(path):
            count = self._oversize_line_count.get(path, 0)
            yield LintFinding(
                rule_id=self.rule_id,
                severity=self.severity,
                file=str(path),
                line=1,
                message=(
                    f"SKILL body exceeds {_MAX_LINES}-line budget "
                    f"({count} lines) — trim prose Claude already knows "
                    "or split into references/*.md."
                ),
            )
        for pattern in _MIRRORED_HEADINGS:
            if pattern.match(line):
                yield LintFinding(
                    rule_id=self.rule_id,
                    severity=self.severity,
                    file=str(path),
                    line=lineno,
                    message=(
                        f"SKILL inlines mirrored heading {line.strip()!r} — "
                        "link to references/*.md instead of duplicating the prose."
                    ),
                )


SPEC = LintSpec(
    rule_id=_RULE_ID,
    roots=(".cursor/skills", ".claude/skills"),
    text_checkers=(SizeAndDisclosureChecker(),),
    file_glob="SKILL.md",
)


analyze = SPEC.analyze
compare_baseline = SPEC.compare_baseline


def main() -> None:
    _base.run_lint_cli(SPEC)


if __name__ == "__main__":
    cli.run_main(main)
