#!/usr/bin/env python3
"""Lint: review SKILL.md bodies wire the human-approval ceremony.

Usage:
  .spec-workflow/sdd internal_lints/approve_ceremony_wired.py            — scan SKILL.md bodies, fail on new findings.
  .spec-workflow/sdd internal_lints/approve_ceremony_wired.py --refresh  — rewrite the baseline to observed findings.

Two failure modes per SKILL.md body:

1. The SKILL invokes ``approval/update-status.py … approve`` but does
   not also reference ``human-approval-ceremony.md`` or the canonical
   prompt id ``approval-confirm-human``. Without the ceremony reference
   the agent skips the H1 gate.
2. The SKILL.md body mentions ``render_prompt_for_harness`` — the
   Python API must not appear in SKILL bodies. Render the prompt via
   the executable shim ``.spec-workflow/sdd util/generate-prompt.py``
   instead.
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

_APPROVE_INVOCATION_RE = re.compile(
    r"approval/update-status\.py.*\bapprove\b",
)
_PYTHON_API_RE = re.compile(r"render_prompt_for_harness")
_CEREMONY_REF_RE = re.compile(r"human-approval-ceremony\.md|approval-confirm-human")


class CeremonyChecker:
    """File-aware text checker — uses ``prepare()`` to resolve once per file.

    The "approve invocation without ceremony reference" check is
    file-level (does this body mention the ref doc anywhere?), so the
    file-level state is computed in ``prepare()`` and reused per-line.
    """

    rule_id = _RULE_ID
    severity = "error"

    def __init__(self) -> None:
        self._has_ceremony: dict[Path, bool] = {}

    def prepare(self, path: Path, text: str) -> None:
        self._has_ceremony[path] = bool(_CEREMONY_REF_RE.search(text))

    def check_line(
        self, line: str, lineno: int, path: Path,
    ) -> Iterable[LintFinding]:
        if (
            _APPROVE_INVOCATION_RE.search(line)
            and not self._has_ceremony.get(path, False)
        ):
            yield LintFinding(
                rule_id=self.rule_id,
                severity=self.severity,
                file=str(path),
                line=lineno,
                message=(
                    "approve invocation without ceremony reference — link "
                    "human-approval-ceremony.md or render approval-confirm-human."
                ),
            )
        if _PYTHON_API_RE.search(line):
            yield LintFinding(
                rule_id=self.rule_id,
                severity=self.severity,
                file=str(path),
                line=lineno,
                message=(
                    "render_prompt_for_harness in SKILL body — invoke via "
                    "util/generate-prompt.py through the shim instead."
                ),
            )


SPEC = LintSpec(
    rule_id=_RULE_ID,
    roots=(".cursor/skills", ".claude/skills"),
    text_checkers=(CeremonyChecker(),),
    file_glob="SKILL.md",
)


def _scan_skill_md(path: Path) -> list[LintFinding]:
    """Single-path scan kept for unit-test back-compat.

    Allocates a fresh checker per call so per-file ``prepare()`` state
    does not bleed across tests.
    """
    return _base.scan_text_file(Path(path), (CeremonyChecker(),))


analyze = SPEC.analyze
compare_baseline = SPEC.compare_baseline


def main() -> None:
    _base.run_lint_cli(SPEC)


if __name__ == "__main__":
    cli.run_main(main)
