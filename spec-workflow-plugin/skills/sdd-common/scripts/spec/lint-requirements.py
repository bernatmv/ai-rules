#!/usr/bin/env python3
"""Validate requirements.md: antipattern linter (pre-review).

Thin CLI wrapper around :mod:`sdd_core.requirements_validation`.
Mode detection delegates to :func:`sdd_core.specs.is_bug_fix_spec`.

Usage:
  lint-requirements.py <requirements.md>
  lint-requirements.py --target <spec-name>
  lint-requirements.py --target <spec-name> --mode {standard|bug-fix}

Exit codes: see `script-conventions.md` § Exit Codes — canonical policy
(0 = success/warn/info, 1 = errors or user error, 2 = system error).
"""

from __future__ import annotations

import _bootstrap  # noqa: F401

import json

import os

from skill_helpers import safe_open
from sdd_core import cli, handoffs, output, paths
from sdd_core.command_templates import build_lint_requirements_command
from sdd_core.lint_view import truncate_issues_for_context
from sdd_core.paths import pre_launch_findings_path, spec_name_from_doc_path

# Mirrors workflow-graph.json `sdd-create-spec.context_needs`.
__sdd_context_needs__ = ("target", "workspace")
from sdd_core.requirements_validation import (
    MODE_BUG_FIX,
    MODE_STANDARD,
    build_structured_findings,
    validate_content,
)
from sdd_core.specs import is_bug_fix_spec
from sdd_core.time import ts_now


_VALID_MODES = (MODE_STANDARD, MODE_BUG_FIX)


def _persist_findings_file(
    *, category: str, target_name: str | None, project_path: str,
    outcome_result: str, counts: dict, findings: list,
) -> str | None:
    """Write ``.pre-launch-findings.json`` next to the doc; remove on pass.

    Returns the absolute path (if written) or ``None`` when the file was
    cleaned up (pass) or persistence was not possible (missing spec_name).
    """
    if not target_name:
        return None
    findings_path = pre_launch_findings_path(category, target_name, project_path)
    if outcome_result in ("fail", "warn"):
        try:
            output.atomic_write_json(findings_path, {
                "generated_at": ts_now(),
                "spec_name": target_name,
                "overall": outcome_result.upper(),
                "counts": counts,
                "findings": findings,
            })
            return findings_path
        except OSError:
            # Persistence is best-effort; validator still emits inline findings.
            return None
    if os.path.exists(findings_path):
        try:
            os.remove(findings_path)
        except OSError:
            pass
    return None


def main() -> None:
    parser = cli.strict_parser(__doc__)
    parser.add_argument("requirements_file", nargs="?", default=None,
                        help="Path to requirements.md")
    cli.target_argument(parser, family="spec", required=False)
    parser.add_argument(
        "--mode", choices=list(_VALID_MODES), default=None,
        help="Explicit mode override (default: auto-detect from spec name)",
    )
    args = parser.parse_args()
    ctx = cli.resolve_context(args, needs=__sdd_context_needs__)

    req_file = args.requirements_file
    if not req_file and getattr(args, "spec_name", None):
        req_file = f".spec-workflow/specs/{args.spec_name}/requirements.md"
    if not req_file:
        output.error(
            "Either <requirements_file> or --target <spec-name> is required",
            hint=(
                "Usage: lint-requirements.py <path> or "
                "lint-requirements.py --target <name>"
            ),
        )

    spec_name = args.spec_name or spec_name_from_doc_path(req_file)

    if args.mode is not None:
        mode = args.mode
    elif spec_name and is_bug_fix_spec(spec_name):
        mode = MODE_BUG_FIX
    else:
        mode = MODE_STANDARD

    with safe_open(req_file) as f:
        content = f.read()

    outcome = validate_content(content, mode=mode, spec_name=spec_name)
    counts = outcome["counts"]
    errors = counts["errors"]
    warnings = counts["warnings"]
    infos = counts["infos"]

    summary = (
        f"({errors} errors, {warnings} warnings, {infos} info) "
        f"mode={outcome['mode']} file={req_file}"
    )

    project_path = paths.resolve_project_path(args)
    findings = build_structured_findings(outcome["issues"], content)
    findings_file = _persist_findings_file(
        category="spec",
        target_name=spec_name,
        project_path=project_path,
        outcome_result=outcome["result"],
        counts=counts,
        findings=findings,
    )

    if errors > 0:
        issues = outcome["issues"]
        head_issues, issues_truncated = truncate_issues_for_context(issues)
        head_findings, _ = truncate_issues_for_context(findings)
        retry_cmd = (
            build_lint_requirements_command(
                spec_name=spec_name,
                project_path=project_path or ".",
                mode=outcome["mode"],
            )
            if spec_name
            else ""
        )
        output.error(
            f"FAIL {summary}",
            hint="Fix structural / path errors then re-run.",
            context=json.dumps({
                "counts": counts,
                "mode": outcome["mode"],
                "issues": head_issues,
                "truncated": issues_truncated,
                "findings": head_findings,
                "findings_file": findings_file,
            }),
            next_action_command=retry_cmd,
        )

    label = "PASS" if outcome["result"] == "pass" else "WARN"
    output.success(
        {
            "result": outcome["result"],
            "mode": outcome["mode"],
            "counts": counts,
            "issues": outcome["issues"],
            "findings": findings,
            "findings_file": findings_file,
            "spec_name": spec_name,
        },
        f"{label} {summary}",
        ctx=ctx,
        resolved_from=dict(ctx.resolved_from),
        handoffs=handoffs.handoffs_for(handoffs.current_script_id(), ctx),
    )


if __name__ == "__main__":
    cli.run_main(main)
