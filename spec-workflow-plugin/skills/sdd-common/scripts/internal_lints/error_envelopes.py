#!/usr/bin/env python3
""""Solve, don't punt" lint for ``output.error(...)`` calls.

Walks every executable script under ``.cursor/skills/sdd-common/scripts``
(see :data:`DEFAULT_ROOTS`) and flags any ``output.error(...)`` call
whose kwargs do not include ``next_action_command=`` — unless:

* the call has a legacy ``hint=`` kwarg (soft remediation), or
* the source line or its neighbours carry a
  ``# noqa: solve-dont-punt — <reason>`` annotation.

Rationale: an error envelope that doesn't name the remedy forces the
agent to reconstruct it from prose and often fails silently.
``next_action_command=`` is the preferred form; ``hint=`` is accepted
as a transitional remediation.

Three rule ids surface: ``error-envelope-missing-next-action`` (the
hard error), ``error-envelope-hint-only`` (legacy soft remediation),
and ``error-envelope-exempt`` (noqa-suppressed). Only the exempt set
is baselined; new errors and hint-only findings always surface.

Usage:
  error_envelopes.py            — scan and diff against baseline.
  error_envelopes.py --refresh  — rewrite the baseline.
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from internal_lints import LintFinding
from internal_lints import base as _base
from internal_lints.base import LintSpec
from internal_lints.baseline import (
    MANIFEST_PATH,
    diff_baseline,
    key_for,
    read_baseline,
    write_baseline,
)
from sdd_core import cli, output

from internal_lints._dispatch import rule_id_for

__all__ = [
    "LintFinding",
    "RULE_ID",
    "RULE_ID_MISSING",
    "RULE_ID_HINT_ONLY",
    "RULE_ID_EXEMPT",
    "DEFAULT_ROOTS",
    "max_exemptions",
    "SPEC",
    "analyze",
    "compare_baseline",
    "scan_file",
    "collect_exemption_keys",
    "read_baseline",
    "BASELINE_PATH",
]


RULE_ID = rule_id_for(__name__, __file__)
RULE_ID_MISSING = "error-envelope-missing-next-action"
RULE_ID_HINT_ONLY = "error-envelope-hint-only"
RULE_ID_EXEMPT = "error-envelope-exempt"

_NOQA_RE = re.compile(
    r"#\s*noqa:\s*solve-dont-punt(?:\s*[\u2014\-]\s*(?P<reason>.+))?",
    re.IGNORECASE,
)

DEFAULT_ROOTS: tuple[str, ...] = (
    "pipeline_phases",
    "util",
    "spec",
    "approval",
    "workspace",
    "template",
    "review",
    "discovery",
    "prd",
    "impl",
    "review_quality",
    "sdd_core",
)

# Roots resolved relative to ``scripts/`` (the dir holding this lint).
_SCRIPTS_ROOT = Path(__file__).resolve().parents[1]


def _scripts_relative_roots() -> tuple[str, ...]:
    """Return :data:`DEFAULT_ROOTS` rebased to repo-relative paths."""
    try:
        rel = _SCRIPTS_ROOT.relative_to(
            _base._resolve_repo().resolve()
        )
    except ValueError:
        rel = _SCRIPTS_ROOT
    return tuple(str(rel / r) for r in DEFAULT_ROOTS)


@dataclass(frozen=True)
class _CallInfo:
    line: int
    end_line: int
    has_hint: bool
    has_next_action: bool


def _is_output_error_call(node: ast.Call) -> bool:
    """Return True when *node* is ``output.error(...)``.

    Also matches ``_output.error`` and ``sdd_core.output.error``
    (occasional import styles) so the lint does not silently skip
    calls that used a different alias.
    """
    func = node.func
    if isinstance(func, ast.Attribute) and func.attr == "error":
        value = func.value
        if isinstance(value, ast.Name) and value.id in {"output", "_output"}:
            return True
        if isinstance(value, ast.Attribute) and value.attr == "output":
            return True
    return False


def _call_info(node: ast.Call) -> _CallInfo:
    kwarg_names = {kw.arg for kw in node.keywords if kw.arg}
    return _CallInfo(
        line=node.lineno,
        end_line=getattr(node, "end_lineno", node.lineno) or node.lineno,
        has_hint="hint" in kwarg_names,
        has_next_action="next_action_command" in kwarg_names,
    )


def _has_noqa(source_lines: list[str], start: int, end: int) -> tuple[bool, str]:
    """Return (suppressed, rationale).

    Inspects the call's source range plus the immediately preceding
    line so comments above the call count as exemptions too.
    """
    lo = max(start - 2, 0)
    hi = min(end, len(source_lines))
    for idx in range(lo, hi):
        match = _NOQA_RE.search(source_lines[idx])
        if match:
            reason = (match.group("reason") or "").strip()
            return True, reason
    return False, ""


class _ErrorEnvelopeChecker:
    """Categorise every ``output.error(...)`` site as missing/hint-only/exempt.

    Caches per-file source lines so noqa detection does not re-read the
    file once per call site.
    """

    rule_id = RULE_ID
    severity = "info"

    def __init__(self) -> None:
        self._source_cache: dict[Path, list[str]] = {}

    def _source_for(self, path: Path) -> list[str]:
        cached = self._source_cache.get(path)
        if cached is not None:
            return cached
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            text = ""
        lines = text.splitlines()
        self._source_cache[path] = lines
        return lines

    def check(
        self, node: ast.AST, path: Path,
    ) -> Iterable[LintFinding]:
        if not isinstance(node, ast.Call) or not _is_output_error_call(node):
            return
        info = _call_info(node)
        source = self._source_for(path)
        suppressed, reason = _has_noqa(source, info.line, info.end_line)
        if suppressed:
            yield LintFinding(
                rule_id=RULE_ID_EXEMPT,
                severity="info",
                file=str(path),
                line=info.line,
                message=(
                    f"output.error(...) exempt via noqa: solve-dont-punt — "
                    f"{reason or 'no rationale'}"
                ),
                extra={"reason": reason},
            )
            return
        if info.has_next_action:
            return
        if info.has_hint:
            yield LintFinding(
                rule_id=RULE_ID_HINT_ONLY,
                severity="info",
                file=str(path),
                line=info.line,
                message=(
                    "output.error(...) uses legacy `hint=` without "
                    "`next_action_command=` — prefer a literal shim "
                    "command so the agent doesn't reconstruct it."
                ),
            )
            return
        yield LintFinding(
            rule_id=RULE_ID_MISSING,
            severity="error",
            file=str(path),
            line=info.line,
            message=(
                "output.error(...) has no `next_action_command=` or "
                "`hint=` kwarg — either add a literal recovery command "
                "(preferred) or annotate with "
                "`# noqa: solve-dont-punt — <reason>`."
            ),
        )


SPEC = LintSpec(
    rule_id=RULE_ID,
    roots=_scripts_relative_roots(),
    checkers=(_ErrorEnvelopeChecker(),),
    exclude_parts=("__pycache__", "migrations"),
)


def scan_file(path: Path) -> list[LintFinding]:
    """Return findings for one ``*.py`` file (test-friendly entry point)."""
    return _base.scan_file(path, SPEC.checkers)


def analyze(repo_root: "Path | str | None" = None) -> list[LintFinding]:
    """Run the lint across the scripts tree.

    Roots default to :data:`DEFAULT_ROOTS` resolved under the workflow
    root; tests pass an explicit *repo_root* to lint a fixture.
    """
    return _base.analyze_with_spec(SPEC, repo_root)


def collect_exemption_keys(findings: Iterable[LintFinding]) -> list[str]:
    """Return sorted canonical keys for every exempt finding."""
    return sorted({
        key_for(f) for f in findings if f.rule_id == RULE_ID_EXEMPT
    })


def compare_baseline(
    findings: Iterable[LintFinding],
    *,
    manifest_path: "Path | str | None" = None,
) -> dict[str, list[str]]:
    """Diff observed exemptions against the rule's manifest entries.

    Only ``RULE_ID_EXEMPT`` findings count toward the baseline — new
    errors and hint-only findings always surface.
    """
    target = Path(manifest_path) if manifest_path is not None else None
    observed = collect_exemption_keys(list(findings))
    return diff_baseline(observed, rule_id=RULE_ID, manifest_path=target)


def max_exemptions() -> int:
    """Exemption ceiling derived from the manifest's entries for this rule."""
    return len(read_baseline(RULE_ID))


def main() -> None:
    parser = cli.strict_parser(__doc__)
    parser.add_argument(
        "--refresh", action="store_true",
        help="Rewrite the baseline to match observed exemptions.",
    )
    parser.add_argument(
        "--strict", action="store_true",
        help=(
            "Fail when any call lacks a remediation. Default behaviour "
            "fails only when exemption baseline drifts."
        ),
    )
    args = parser.parse_args()

    findings = analyze()
    if args.refresh:
        observed = collect_exemption_keys(findings)
        write_baseline(RULE_ID, observed)
        output.success(
            {"rule_id": RULE_ID, "count": len(observed)},
            f"{RULE_ID}: baseline refreshed",
        )
        return

    errors = [f for f in findings if f.severity == "error"]
    exemptions = [f for f in findings if f.rule_id == RULE_ID_EXEMPT]
    hint_only = [f for f in findings if f.rule_id == RULE_ID_HINT_ONLY]
    diff = compare_baseline(findings)
    baseline_ok = not diff["new"] and not diff["stale"]
    strict_ok = not errors
    ok = baseline_ok and (not args.strict or strict_ok)

    payload = {
        "ok": ok,
        "error_count": len(errors),
        "hint_only_count": len(hint_only),
        "exemption_count": len(exemptions),
        "new_exemptions": diff["new"],
        "stale_exemptions": diff["stale"],
        "known_exemptions": diff["known"],
        "strict": args.strict,
        "findings": [f.to_payload() for f in findings],
    }
    message = (
        f"{RULE_ID}: {len(errors)} error(s), "
        f"{len(hint_only)} hint-only, "
        f"{len(exemptions)} exemption(s) "
        f"({len(diff['new'])} new, {len(diff['stale'])} stale)"
    )
    if ok:
        output.result(payload, message, exit_code=0)
        return
    from sdd_core.command_templates import build_baseline_refresh_command
    next_cmd = build_baseline_refresh_command(RULE_ID)
    output.error(
        message,
        hint=(
            "Fix the new findings or refresh the baseline. "
            "Strict mode requires every call to carry a remediation."
        ),
        next_action_command=next_cmd,
    )


BASELINE_PATH = MANIFEST_PATH


if __name__ == "__main__":
    cli.run_main(main)
