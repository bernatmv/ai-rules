#!/usr/bin/env python3
"""Lint: SKILL.md and references/ may not carry plan-trace prose.

References must describe the **current** contract from a reader's POV.
Markdown that names a workstream id ("WS-3"), a rollout-cycle tag
("RC-4"), a PR number ("PR-1234"), or a "prior memo / prior plan"
hand-off rots within weeks: the reader has no way to look up the
referent once the merge queue has moved past it, and Claude reads
such prose as if the project were mid-flight. Maintenance details
that are genuinely useful belong in a clearly-labelled
``## Maintainer notes`` section, not interleaved with the contract.

Existing matches live in the baseline; new matches fail the lint
until either rewritten or moved under a Maintainer-notes heading.

Usage:
  no_plan_trace_in_references.py            — scan and diff against baseline.
  no_plan_trace_in_references.py --refresh  — rewrite the baseline.
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import re
from pathlib import Path

from internal_lints import LintFinding
from internal_lints._dispatch import rule_id_for
from internal_lints.baseline import (
    diff_baseline,
    key_for,
    read_baseline,
    write_baseline,
)
from sdd_core import cli, output

_RULE_ID = rule_id_for(__name__, __file__)

_LINT_FILE = Path(__file__).resolve()
_SKILLS_ROOT = _LINT_FILE.parent.parent.parent.parent  # …/.cursor/skills/

# One scan root per skill — the lint covers SKILL.md + everything under
# references/. Adding a new SDD-family skill is a one-line append here.
_SCAN_ROOTS: tuple[str, ...] = (
    "sdd-common",
    "sdd-workspace-create-spec",
    "sdd-create-spec",
)

_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    # Workstream and rollout-cycle ids — short tags that rot once the
    # plan they reference is merged. Walk both the legacy ``RC``/``WS``
    # vocabulary and the newer ``AS``/``R-`` workstream ids so prose
    # stops carrying lineage that belongs in the PR description.
    ("as-tag", re.compile(r"\bAS-\d+")),
    ("rc-tag", re.compile(r"\bRC-\d+")),
    ("pr-tag", re.compile(r"\bPR-\d+")),
    ("ws-tag", re.compile(r"\bWS-\d+")),
    # ``R-1`` … ``R-9`` — recurrence ids; a one-letter prefix is too
    # ambiguous so we cap the digit count to 1 to keep false-positives
    # below noise. Multi-digit recurrence ids do not exist in this repo.
    ("r-tag", re.compile(r"\bR-[1-9]\b")),
    # ``RCA N-3`` and ``RCA N-3.1`` — RCA finding ids.
    ("rca-finding", re.compile(r"\bRCA\s+N-\d+")),
    ("prior-memo", re.compile(r"prior memo", re.IGNORECASE)),
    ("prior-plan", re.compile(r"prior plan", re.IGNORECASE)),
    ("systematic-tightening", re.compile(r"systematic-tightening")),
    ("added-in-commit", re.compile(r"added in (?:commit|PR)\b", re.IGNORECASE)),
    ("fixes-commit", re.compile(r"fixes (?:commit|PR)\b", re.IGNORECASE)),
    ("see-commit", re.compile(r"see (?:commit|PR)\b", re.IGNORECASE)),
)

# A line under a "Maintainer notes" heading is an explicit contributor-
# facing carve-out — the reader is told this content is for maintainers,
# not for inferring current behaviour.
_MAINTAINER_HEADING = re.compile(r"^#+\s*Maintainer notes\b", re.IGNORECASE)


_SCOPE_REFERENCES: str = "references"
_SCOPE_SCRIPTS: str = "scripts"
_SCOPE_ALL: str = "all"
_SCOPES: tuple[str, ...] = (_SCOPE_REFERENCES, _SCOPE_SCRIPTS, _SCOPE_ALL)


def _iter_target_files(scope: str = _SCOPE_REFERENCES) -> list[Path]:
    """Return the file inventory for *scope*.

    ``references`` (default) — SKILL.md plus everything under
    ``references/`` for each scanned skill.
    ``scripts`` — every ``*.py`` under ``sdd-common/scripts/``
    (Maintainer-notes carve-out still applies via heading detection).
    ``all`` — union of the two.
    """
    out: list[Path] = []
    if scope in (_SCOPE_REFERENCES, _SCOPE_ALL):
        for skill in _SCAN_ROOTS:
            skill_root = _SKILLS_ROOT / skill
            if not skill_root.is_dir():
                continue
            skill_md = skill_root / "SKILL.md"
            if skill_md.is_file():
                out.append(skill_md)
            ref_root = skill_root / "references"
            if ref_root.is_dir():
                out.extend(sorted(ref_root.rglob("*.md")))
    if scope in (_SCOPE_SCRIPTS, _SCOPE_ALL):
        scripts_root = _SKILLS_ROOT / "sdd-common" / "scripts"
        if scripts_root.is_dir():
            for path in sorted(scripts_root.rglob("*.py")):
                if "__pycache__" in path.parts:
                    continue
                # The lint module's own pattern strings are not plan
                # traces — skip the scanner so it doesn't flag itself.
                if path == _LINT_FILE:
                    continue
                out.append(path)
    return out


def _scan_file(path: Path) -> list[LintFinding]:
    """Return one finding per offending line outside Maintainer-notes."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    findings: list[LintFinding] = []
    in_maintainer_section = False
    try:
        rel = str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        rel = str(path)
    for lineno, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("#"):
            in_maintainer_section = bool(_MAINTAINER_HEADING.match(line.strip()))
        if in_maintainer_section:
            continue
        for label, pattern in _PATTERNS:
            if pattern.search(line):
                findings.append(LintFinding(
                    rule_id=_RULE_ID,
                    severity="error",
                    file=rel,
                    line=lineno,
                    message=(
                        f"line carries plan-trace prose ({label}): "
                        f"{line.strip()!r}. Rewrite as a present-tense "
                        "contract or move under a `## Maintainer notes` "
                        "heading."
                    ),
                    extra={"reason": label},
                ))
                break
    return findings


def analyze(scope: str = _SCOPE_REFERENCES) -> list[LintFinding]:
    findings: list[LintFinding] = []
    for path in _iter_target_files(scope):
        findings.extend(_scan_file(path))
    return findings


def _emit_envelope(findings: list[LintFinding], *, refresh: bool) -> None:
    observed = sorted({key_for(f) for f in findings})
    if refresh:
        write_baseline(_RULE_ID, observed)
        output.success(
            {"rule_id": _RULE_ID, "count": len(observed)},
            f"{_RULE_ID}: baseline refreshed",
        )
        return
    diff = diff_baseline(observed, rule_id=_RULE_ID)
    if diff["new"] or diff["stale"]:
        output.error(
            f"{_RULE_ID}: new={len(diff['new'])} stale={len(diff['stale'])}",
            hint=(
                "Rewrite the line as a present-tense contract, move it "
                "under a `## Maintainer notes` heading, or refresh the "
                "baseline if the finding is expected."
            ),
            next_action_command=(
                f".spec-workflow/sdd internal_lints/baseline-refresh.py "
                f"--rule {_RULE_ID}"
            ),
        )
    output.success({"known": diff["known"]}, f"{_RULE_ID}: clean")


def main() -> None:
    parser = cli.strict_parser(
        "Forbid plan-trace prose in SKILL.md / references/ / scripts/"
    )
    parser.add_argument(
        "--refresh", action="store_true",
        help="Rewrite the baseline to match observed findings.",
    )
    parser.add_argument(
        "--scope",
        choices=_SCOPES,
        default=_SCOPE_REFERENCES,
        help=(
            "Which file set to scan: 'references' (default) walks "
            "SKILL.md + references/; 'scripts' walks "
            "sdd-common/scripts/*.py; 'all' walks both."
        ),
    )
    args = parser.parse_args()
    findings = analyze(args.scope)
    _emit_envelope(findings, refresh=args.refresh)


if __name__ == "__main__":
    cli.run_main(main)
