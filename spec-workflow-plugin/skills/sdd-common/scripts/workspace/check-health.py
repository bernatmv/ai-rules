#!/usr/bin/env python3
"""Workspace health check CLI.

Thin wrapper around :mod:`sdd_core.workspace_health_checks`: all check
implementations, the ``@register_check`` registry, and autofix
orchestration live in the library; this file parses arguments and
formats the final JSON envelope.

Usage:
    .spec-workflow/sdd workspace/check-health.py [--auto-fix] [--dry-run] [--workspace PATH]

Outputs structured JSON with a top-level ``healthy`` boolean and a
``checks`` array.  With ``--auto-fix`` it repairs what it can and then
re-evaluates to confirm success.  With ``--dry-run`` detection runs but
repair is skipped.
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

from pathlib import Path

from sdd_core import cli, handoffs, output, paths
from sdd_core.paths import WORKFLOW_DIR
from sdd_core import workspace_health_checks as checks

# Workspace-only shim: no target / repo_id / phase consumed.
__sdd_context_needs__ = ("workspace",)


def main() -> None:
    parser = cli.strict_parser("Workspace health check")
    parser.add_argument("--auto-fix", action="store_true", help="Attempt to repair issues")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be repaired without making changes",
    )
    parser.add_argument(
        "--force-template-repair",
        action="store_true",
        help=(
            "Allow auto-fix to overwrite drifted templates. Backups land "
            "under .spec-workflow/.backup/templates-{ts}/ before replace."
        ),
    )
    args = parser.parse_args()
    ctx = cli.resolve_context(args, needs=("workspace",))

    if args.auto_fix and args.dry_run:
        output.error("--auto-fix and --dry-run are mutually exclusive")

    root = Path(paths.resolve_project_path(args)).resolve()
    workflow = root / WORKFLOW_DIR
    if not workflow.is_dir():
        output.error(
            f"No {WORKFLOW_DIR}/ directory found at {root}",
            hint="Run workspace/init.py first, or use workspace/ensure-healthy.py",
        )

    result = checks.run_all_checks(
        root,
        auto_fix=args.auto_fix,
        dry_run=args.dry_run,
        force_template_repair=args.force_template_repair,
    )

    if args.auto_fix and not result["healthy"]:
        result = checks.run_autofix_and_reverify(root, result)

    if result["healthy"]:
        output.success(
            result,
            "Workspace is healthy",
            ctx=ctx,
            resolved_from=dict(ctx.resolved_from),
            handoffs=handoffs.handoffs_for(handoffs.current_script_id(), ctx),
        )
    else:
        failing = [c["name"] for c in result["checks"] if c["status"] == "fail"]
        output.result(
            result,
            f"Workspace has issues: {', '.join(failing)}",
            exit_code=1,
        )


if __name__ == "__main__":
    cli.run_main(main)
