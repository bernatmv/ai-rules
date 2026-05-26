#!/usr/bin/env python3
"""Lint: skill prose must not teach CLI shapes that aren't emitter-produced.

Operates in two modes:

* ``--mode denylist`` (default) — flags lines containing rejected
  snippet patterns enumerated in :data:`_REJECTED_PATTERNS`. Patterns
  are surfaced with a hint pointing at the canonical emitter so the
  fix is mechanical.
* ``--mode allowlist`` — renders every ``command_templates.build_*``
  builder against ``emitter_fixtures.yaml``, collects the
  ``<group>/<script>.py`` shape of each emitted literal, and asserts
  that every ``bash`` / ```` ``` ````-fenced shim invocation in
  ``references/**/*.md`` matches at least one collected shape.
  Findings carry a ``did_you_mean`` pointing at the closest emitter
  shape so a documentation change is mechanical to fix. Markdown
  blocks marked with the
  ``<!-- prose-invocation: rejected-by-design -->`` HTML comment are
  exempt — used to illustrate rejected shapes in troubleshooting docs.

Each pattern's baseline lives in
``internal_lints/baselines.json::rules.prose-invocation-via-emitter``.

Usage:
  prose_invocation_via_emitter.py                       — denylist diff against baseline.
  prose_invocation_via_emitter.py --refresh             — rewrite the baseline.
  prose_invocation_via_emitter.py --mode allowlist      — allowlist diff.
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import difflib
import re
from pathlib import Path
from typing import Iterable

from internal_lints import LintFinding
from internal_lints._dispatch import rule_id_for
from internal_lints.base import LintSpec, run_text_lint
from sdd_core import cli

_RULE_ID = rule_id_for(__name__, __file__)


_REJECTED_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "--tracker-root coordinator --tracker-target",
        re.compile(
            r"--tracker-root\s+coordinator\s+--tracker-target",
        ),
        (
            "Use the coordinator-rooted form `--workspace "
            "{coordinator-path} --target {feature}/{repo-id}` instead. "
            "Canonical literal is emitted by "
            "`command_templates.build_check_spec_shape_command`."
        ),
    ),
)


_REJECTED_BY_DESIGN_MARKER = "prose-invocation: rejected-by-design"


class _ProseInvocationChecker:
    rule_id = _RULE_ID
    severity = "error"

    def check_line(
        self, line: str, lineno: int, path: Path,
    ) -> Iterable[LintFinding]:
        findings: list[LintFinding] = []
        for label, pattern, hint in _REJECTED_PATTERNS:
            if not pattern.search(line):
                continue
            findings.append(LintFinding(
                rule_id=self.rule_id,
                severity=self.severity,
                file=str(path),
                line=lineno,
                message=(
                    f"Skill prose teaches a non-emitter invocation "
                    f"({label!r}). {hint}"
                ),
            ))
        return findings


SPEC = LintSpec(
    rule_id=_RULE_ID,
    roots=(".cursor/skills",),
    text_checkers=(_ProseInvocationChecker(),),
    file_glob="*.md",
)


analyze = SPEC.analyze
compare_baseline = SPEC.compare_baseline


_SHIM_PREFIX = ".spec-workflow/sdd "
_FENCE_BASH_RE = re.compile(r"^```(?:bash|sh|shell)?\s*$")
_FENCE_END_RE = re.compile(r"^```\s*$")


def _allowed_shapes() -> set[str]:
    """Render every emitter against ``emitter_fixtures.yaml`` and collect shapes.

    Each rendered literal's first non-prefix token (the
    ``<group>/<script>.py`` form) is taken as the canonical shape. An
    emitter that raises on render is skipped — :mod:`emitted_commands_parse`
    is the gate for those failures.
    """
    from sdd_core import command_templates
    from sdd_core.data_loader import load_yaml

    payload = load_yaml("emitter_fixtures.yaml")
    raw = payload.get("emitters") if isinstance(payload, dict) else {}
    if not isinstance(raw, dict):
        return set()
    shapes: set[str] = set()
    for name, row in raw.items():
        if not isinstance(row, dict) or "skip" in row:
            continue
        builder = getattr(command_templates, name, None)
        if builder is None:
            continue
        kwargs = dict(row.get("kwargs") or {})
        try:
            rendered = builder(**kwargs)
        except Exception:
            continue
        if not isinstance(rendered, str) or not rendered.startswith(_SHIM_PREFIX):
            continue
        rest = rendered[len(_SHIM_PREFIX):].lstrip()
        if not rest:
            continue
        token = rest.split(None, 1)[0]
        if token:
            shapes.add(token)
    return shapes


def _iter_shim_lines(text: str) -> Iterable[tuple[int, str, bool]]:
    """Yield ``(lineno, line, in_fence)`` for every shim-bearing prose line.

    Fenced blocks marked rejected-by-design via an HTML comment
    immediately above the opening fence are skipped. Inline shim
    invocations (outside fenced blocks) are also surfaced so prose
    paragraphs that name a literal stay validated.
    """
    lines = text.splitlines()
    in_fence = False
    fence_skip = False
    for idx in range(len(lines)):
        line = lines[idx]
        if _FENCE_BASH_RE.match(line):
            in_fence = True
            fence_skip = False
            # Look back for the rejected-by-design marker.
            for back in range(idx - 1, max(idx - 4, -1), -1):
                if not lines[back].strip():
                    continue
                if _REJECTED_BY_DESIGN_MARKER in lines[back]:
                    fence_skip = True
                break
            continue
        if in_fence and _FENCE_END_RE.match(line):
            in_fence = False
            fence_skip = False
            continue
        if _SHIM_PREFIX in line and not fence_skip:
            yield (idx + 1, line, in_fence)


def _extract_shape(line: str) -> str:
    """Pull the ``<group>/<script>.py`` shape from a shim-bearing line."""
    pos = line.find(_SHIM_PREFIX)
    if pos < 0:
        return ""
    rest = line[pos + len(_SHIM_PREFIX):].lstrip()
    if not rest:
        return ""
    token = rest.split(None, 1)[0]
    # Strip trailing markdown punctuation (back-tick, comma, period).
    return token.rstrip("`,.;")


def _did_you_mean(typed: str, allowed: Iterable[str]) -> str:
    candidates = [a for a in allowed if a]
    if not candidates:
        return ""
    matches = difflib.get_close_matches(typed, candidates, n=1, cutoff=0.5)
    return matches[0] if matches else ""


def _allowlist_findings(repo_root: Path) -> list[LintFinding]:
    """Walk ``references/**/*.md`` and flag shim shapes outside the allowlist."""
    allowed = _allowed_shapes()
    if not allowed:
        return []
    findings: list[LintFinding] = []
    skills_root = repo_root / ".cursor" / "skills"
    if not skills_root.is_dir():
        return findings
    for ref_dir in sorted(skills_root.glob("*/references")):
        for md_path in sorted(ref_dir.rglob("*.md")):
            try:
                text = md_path.read_text(encoding="utf-8")
            except OSError:
                continue
            for lineno, line, _in_fence in _iter_shim_lines(text):
                shape = _extract_shape(line)
                if not shape or "/" not in shape or not shape.endswith(".py"):
                    continue
                if shape in allowed:
                    continue
                suggestion = _did_you_mean(shape, allowed)
                msg = (
                    f"Prose teaches shim shape {shape!r} which no "
                    "emitter in command_templates produces."
                )
                if suggestion:
                    msg += f" did_you_mean: {suggestion!r}."
                findings.append(LintFinding(
                    rule_id=_RULE_ID,
                    severity="error",
                    file=str(md_path),
                    line=lineno,
                    message=msg,
                ))
    return findings


def _run_allowlist(*, refresh: bool) -> None:
    from internal_lints.base import _emit_envelope, _resolve_repo

    repo = _resolve_repo()
    findings = _allowlist_findings(repo)
    _emit_envelope(SPEC, findings, refresh=refresh)


def main() -> None:
    parser = cli.strict_parser(__doc__ or "")
    parser.add_argument(
        "--refresh", action="store_true",
        help="Rewrite the baseline to match observed findings.",
    )
    parser.add_argument(
        "--mode", choices=("denylist", "allowlist"), default="denylist",
        help="denylist (default): flag rejected snippet patterns. "
             "allowlist: assert every prose shim shape is emitter-produced.",
    )
    args = parser.parse_args()
    if args.mode == "allowlist":
        _run_allowlist(refresh=args.refresh)
        return
    run_text_lint(SPEC, refresh=args.refresh)


if __name__ == "__main__":
    cli.run_main(main)
