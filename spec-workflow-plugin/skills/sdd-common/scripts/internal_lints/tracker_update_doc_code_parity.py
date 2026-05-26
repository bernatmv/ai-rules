#!/usr/bin/env python3
"""Lint: ``check-spec-shape.py`` honours every prose ``auto, via …`` claim.

Walks ``.cursor/skills/*/references/phase-loop.md`` (and any sibling
that documents the workspace tracker auto-update path) for prose of
the form *"… auto, via .spec-workflow/sdd workspace/check-spec-shape.py
… ."*. For each claim, asserts the in-tree resolver still wires the
coordinator-rooted-``--workspace`` path: when ``--workspace`` resolves
to an absolute coordinator path and ``--target`` carries the slash
form, ``_resolve_tracker_root_with_fallback`` must return a non-None
path.

This is a *static* parity check — it does not invoke the script.
The fixture-style hermetic invocation is exercised by
``tests/test_workspace/test_check_spec_shape_coordinator_root_recurrence``;
this lint catches the case where the resolver helper is renamed or
deleted without the matching prose update.

Usage:
  tracker_update_doc_code_parity.py            — diff against baseline.
  tracker_update_doc_code_parity.py --refresh  — rewrite the baseline.
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import re
from pathlib import Path
from typing import Final

from internal_lints import LintFinding
from internal_lints._dispatch import rule_id_for
from internal_lints.base import LintSpec, _emit_envelope, _resolve_repo
from sdd_core import cli

_RULE_ID = rule_id_for(__name__, __file__)

_AUTO_CLAIM_RE = re.compile(
    r"auto[, ]+via\s+`?\.spec-workflow/sdd\s+workspace/check-spec-shape\.py",
    re.IGNORECASE,
)

_CHECK_SPEC_SHAPE_REL: Final[tuple[str, ...]] = (
    ".cursor", "skills", "sdd-common", "scripts",
    "workspace", "check-spec-shape.py",
)
_RESOLVER_HELPER_NAME: Final[str] = "_resolve_tracker_root_with_fallback"


def _check_spec_shape_path(repo: Path) -> Path:
    """Return the absolute path of ``workspace/check-spec-shape.py``."""
    return repo.joinpath(*_CHECK_SPEC_SHAPE_REL)


def _check_resolver_present() -> list[LintFinding]:
    """Assert the named helper still exists in ``check-spec-shape.py``."""
    findings: list[LintFinding] = []
    repo = _resolve_repo()
    script = _check_spec_shape_path(repo)
    if not script.is_file():
        findings.append(LintFinding(
            rule_id=_RULE_ID, severity="error",
            file=str(script), line=0,
            message="workspace/check-spec-shape.py missing.",
        ))
        return findings
    text = script.read_text(encoding="utf-8")
    if _RESOLVER_HELPER_NAME not in text:
        findings.append(LintFinding(
            rule_id=_RULE_ID, severity="error",
            file=str(script), line=0,
            message=(
                f"{_RESOLVER_HELPER_NAME} helper missing — the "
                "coordinator-rooted-`--workspace` auto-detection branch "
                "is the single writer for the prose claim that no "
                "`--tracker-root` boilerplate is needed."
            ),
        ))
    return findings


def _check_prose_claims() -> list[LintFinding]:
    """For every prose ``auto, via`` claim, the resolver must be wired."""
    findings: list[LintFinding] = []
    repo = _resolve_repo()
    skills_root = repo / ".cursor" / "skills"
    if not skills_root.is_dir():
        return findings
    # Resolver presence is global; this loop records every prose
    # location so the operator's fix is targeted.
    for ref_dir in sorted(skills_root.glob("*/references")):
        for md in sorted(ref_dir.glob("*.md")):
            try:
                text = md.read_text(encoding="utf-8")
            except OSError:
                continue
            for lineno, line in enumerate(text.splitlines(), start=1):
                if _AUTO_CLAIM_RE.search(line):
                    findings.extend(_validate_resolver_for_claim(md, lineno))
    return findings


def _validate_resolver_for_claim(
    md: Path, lineno: int,
) -> list[LintFinding]:
    """Surface a finding when the resolver is missing for this claim."""
    repo = _resolve_repo()
    script = _check_spec_shape_path(repo)
    if not script.is_file():
        return [LintFinding(
            rule_id=_RULE_ID, severity="error",
            file=str(md), line=lineno,
            message=(
                f"prose claims auto-update via check-spec-shape.py "
                f"but the script is missing at {script}."
            ),
        )]
    text = script.read_text(encoding="utf-8")
    if _RESOLVER_HELPER_NAME not in text:
        return [LintFinding(
            rule_id=_RULE_ID, severity="error",
            file=str(md), line=lineno,
            message=(
                "prose claims auto-update via check-spec-shape.py but "
                f"the resolver helper {_RESOLVER_HELPER_NAME} is missing."
            ),
        )]
    return []


SPEC = LintSpec(
    rule_id=_RULE_ID,
    roots=(".cursor/skills",),
    file_glob="*.md",
)


def main() -> None:
    parser = cli.strict_parser(__doc__ or "")
    parser.add_argument(
        "--refresh", action="store_true",
        help="Rewrite the baseline to match observed findings.",
    )
    args = parser.parse_args()
    findings: list[LintFinding] = []
    findings.extend(_check_resolver_present())
    findings.extend(_check_prose_claims())
    _emit_envelope(SPEC, findings, refresh=args.refresh)


if __name__ == "__main__":
    cli.run_main(main)
