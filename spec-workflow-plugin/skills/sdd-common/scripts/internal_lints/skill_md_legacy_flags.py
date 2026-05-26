#!/usr/bin/env python3
"""Lint: SKILL.md / references must not mention renamed legacy flags.

V-1 collapses the per-skill flag schemas onto canonical ``--target`` /
``--workspace`` selectors (with the workspace-target slash form
``--target {feature}/{repo-id}``). Doc bodies that still mention
``--feature`` / ``--repo-id`` / ``--target-name`` / ``--target-repo``
/ ``--project-path`` lead the agent to type the legacy flag verbatim
and crash on the first parse — the regression class rerun-7 pinned as
L-1/L-2/L-3.

Carve-outs mirror :mod:`internal_lints.cli_argument_conventions` so the
update-manifest set-repo-role subcommand keeps its allowlisted
``--repo-id`` literal in prose.

Usage:
  skill_md_legacy_flags.py            — diff against baseline.
  skill_md_legacy_flags.py --refresh  — rewrite the baseline.
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import re
from pathlib import Path
from typing import Iterable

from internal_lints import LintFinding
from internal_lints._dispatch import rule_id_for
from internal_lints._legacy_flags import CARVE_OUT_PHRASES
from internal_lints.base import LintSpec, run_text_lint
from sdd_core import cli

_RULE_ID = rule_id_for(__name__, __file__)

_LEGACY_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "--feature",
        re.compile(r"(?<![A-Za-z0-9_-])--feature(?![A-Za-z0-9_-])"),
        "Use the canonical `--target {feature}` selector.",
    ),
    (
        "--repo-id",
        re.compile(r"(?<![A-Za-z0-9_-])--repo-id(?![A-Za-z0-9_-])"),
        (
            "Use the workspace-target slash form `--target {feature}/{repo-id}` "
            "(or the allowlisted `update-manifest.py set-repo-role` subcommand)."
        ),
    ),
    (
        "--target-name",
        re.compile(r"(?<![A-Za-z0-9_-])--target-name(?![A-Za-z0-9_-])"),
        (
            "Workspace shims use `--target`. Review shims still expose "
            "`--target-name` until Phase 2 — keep the literal only in "
            "review/* references."
        ),
    ),
    (
        "--target-repo",
        re.compile(r"(?<![A-Za-z0-9_-])--target-repo(?![A-Za-z0-9_-])"),
        "Removed. Use `--workspace {repo-path}` plus `--target`.",
    ),
    (
        "--project-path",
        re.compile(r"(?<![A-Za-z0-9_-])--project-path(?![A-Za-z0-9_-])"),
        "Renamed to `--workspace` at the runner level.",
    ),
)

_ALLOWLIST_PHRASES: tuple[tuple[str, str], ...] = CARVE_OUT_PHRASES


def _line_allowlisted(flag: str, line: str) -> bool:
    for allow_flag, phrase in _ALLOWLIST_PHRASES:
        if allow_flag == flag and phrase in line:
            return True
    return False


class _LegacyFlagsChecker:
    """Per-line text checker — flags every legacy literal in skill docs."""

    rule_id = _RULE_ID
    severity = "error"

    def check_line(
        self, line: str, lineno: int, path: Path,
    ) -> Iterable[LintFinding]:
        findings: list[LintFinding] = []
        for flag, pattern, hint in _LEGACY_PATTERNS:
            if not pattern.search(line):
                continue
            if _line_allowlisted(flag, line):
                continue
            findings.append(LintFinding(
                rule_id=self.rule_id,
                severity=self.severity,
                file=str(path),
                line=lineno,
                message=f"Legacy flag {flag!r} in skill doc — {hint}",
            ))
        return findings


SPEC = LintSpec(
    rule_id=_RULE_ID,
    roots=(".cursor/skills",),
    text_checkers=(_LegacyFlagsChecker(),),
    file_glob="*.md",
)


analyze = SPEC.analyze
compare_baseline = SPEC.compare_baseline


def main() -> None:
    parser = cli.strict_parser(__doc__ or "")
    parser.add_argument(
        "--refresh", action="store_true",
        help="Rewrite the baseline to match observed findings.",
    )
    args = parser.parse_args()
    run_text_lint(SPEC, refresh=args.refresh)


if __name__ == "__main__":
    cli.run_main(main)
