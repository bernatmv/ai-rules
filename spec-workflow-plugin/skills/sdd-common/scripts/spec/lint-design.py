#!/usr/bin/env python3
"""Lint design.md for acceptance-criteria / task-list / prose-only antipatterns.

Thin CLI wrapper around :mod:`sdd_core.design_validation`. Rule set
ships in ``sdd_core/data/design_antipatterns.yaml``.

Usage:
  lint-design.py <design.md>
  lint-design.py --target <spec-name>

Exit codes mirror lint-requirements.py: exit 0 with
``data.outcome="partial"`` on findings; exit 1 only on user error.
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import json

from skill_helpers import safe_open
from sdd_core import cli, handoffs, output
from sdd_core.design_validation import validate_content
from sdd_core.lint_view import truncate_issues_for_context

# Mirrors workflow-graph.json `sdd-create-spec.context_needs`.
__sdd_context_needs__ = ("target", "workspace")


def main() -> None:
    parser = cli.strict_parser(__doc__)
    parser.add_argument(
        "design_file", nargs="?", default=None,
        help="Path to design.md (defaults to .spec-workflow/specs/<target>/design.md)",
    )
    cli.target_argument(parser, family="spec", required=False)
    args = parser.parse_args()
    ctx = cli.resolve_context(args, needs=__sdd_context_needs__)

    design_file = args.design_file
    if not design_file and getattr(args, "spec_name", None):
        design_file = f".spec-workflow/specs/{args.spec_name}/design.md"
    if not design_file:
        output.error(
            "Either <design_file> or --target <spec-name> is required",
            hint="Usage: lint-design.py <path> or lint-design.py --target <name>",
        )

    with safe_open(design_file) as f:
        content = f.read()

    outcome = validate_content(content)
    counts = outcome["counts"]
    summary = (
        f"({counts['errors']} errors, {counts['warnings']} warnings, "
        f"{counts['infos']} info) file={design_file}"
    )

    head_issues, truncated = truncate_issues_for_context(outcome["issues"])
    payload = {
        "result": outcome["result"],
        "counts": counts,
        "issues": outcome["issues"],
        "truncated": truncated,
        "design_file": design_file,
    }

    if outcome["result"] == "pass":
        output.success(
            payload,
            f"PASS {summary}",
            ctx=ctx,
            resolved_from=dict(ctx.resolved_from),
            handoffs=handoffs.handoffs_for(handoffs.current_script_id(), ctx),
        )
    else:
        # Result-class outcome: emit partial so the parallel-batch
        # cancel cascade does not trigger on lint findings.
        output.partial(
            payload,
            f"{outcome['result'].upper()} {summary}\n"
            f"{json.dumps(head_issues, indent=2)}",
        )


if __name__ == "__main__":
    cli.run_main(main)
