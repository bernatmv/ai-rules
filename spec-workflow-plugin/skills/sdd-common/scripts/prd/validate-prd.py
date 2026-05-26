#!/usr/bin/env python3
"""Validate PRD structural quality.

Usage: validate-prd.py <prd.md>
Exit code: 0 if all checks pass, 1 if issues found, 2 on usage error.

Checks:
- WHEN/THEN format in requirements sections (regex scan)
- Named subject in THEN clauses
- All 6 NFR categories present and non-placeholder
- Open questions have Owner + Due Date + Blocks columns
- Alternatives Considered section non-empty
- Rollout plan has Success Gate + Rollback Plan columns
- Goals table has Metric + Target + Measurement Method columns
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

from sdd_core import cli, handoffs, output
from skill_helpers import safe_open
from prd.shared import extract_sections
from prd.checks import CHECK_REGISTRY

# Mirrors workflow-graph.json `sdd-create-prd.context_needs`.
__sdd_context_needs__ = ("target", "workspace")


def read_content(filepath: str) -> str:
    with safe_open(filepath) as f:
        return f.read()


def main() -> None:
    parser = cli.strict_parser("Validate PRD structural quality")
    parser.add_argument("prd_file", help="Path to prd.md")
    args = parser.parse_args()
    ctx = cli.resolve_context(args, needs=__sdd_context_needs__)

    content = read_content(args.prd_file)
    sections = extract_sections(content)

    all_issues: list[str] = []
    checks: dict[str, str] = {}

    for check in CHECK_REGISTRY:
        input_data = content if check.input_type == "content" else sections
        issues = check.func(input_data)
        checks[check.id] = "pass" if not issues else "fail"
        all_issues.extend(issues)

    data = {
        "result": "issues_found" if all_issues else "all_checks_pass",
        "checks": checks,
        "issues": all_issues,
        "issue_count": len(all_issues),
    }

    if all_issues:
        output.result(
            data,
            f"ISSUES FOUND: {len(all_issues)} structural issue(s)",
            exit_code=1,
        )
    else:
        output.success(
            data,
            "ALL CHECKS PASS",
            ctx=ctx,
            resolved_from=dict(ctx.resolved_from),
            handoffs=handoffs.handoffs_for(handoffs.current_script_id(), ctx),
        )


if __name__ == "__main__":
    cli.run_main(main)
