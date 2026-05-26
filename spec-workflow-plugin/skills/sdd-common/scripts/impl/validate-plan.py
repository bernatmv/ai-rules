#!/usr/bin/env python3
"""Validate an ``edit-plan.json`` produced by ``impl/plan-task.py``.

Part of the plan-validate-execute pipeline.

Checks:
  * required fields, schema_version match
  * each file entry has a path and an allowed action
  * paths are relative and stay inside the workspace
  * paths are not excluded by the top-level ``.gitignore``
  * ``size_delta_estimate`` respects ``--max-size-delta`` unless
    ``--allow-large-delta`` is set

Usage:
    validate-plan.py plan.json [--max-size-delta N] [--allow-large-delta]

Exit code:
  * 0 — plan is valid
  * 1 — plan has validation errors (printed under ``data.errors``)
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

from sdd_core import cli, output, paths
from sdd_core.edit_plans import (
    DEFAULT_SIZE_DELTA_THRESHOLD,
    load_plan,
    validate_plan,
)


def main() -> None:
    parser = cli.strict_parser("Validate an edit-plan.json")
    parser.add_argument("plan_file", help="Path to edit-plan.json")
    parser.add_argument(
        "--max-size-delta",
        type=int,
        default=DEFAULT_SIZE_DELTA_THRESHOLD,
        help=(
            f"Cap on per-file size_delta_estimate "
            f"(default {DEFAULT_SIZE_DELTA_THRESHOLD} lines)"
        ),
    )
    parser.add_argument(
        "--allow-large-delta",
        action="store_true",
        help="Skip the size_delta_estimate cap (use for deliberate big refactors)",
    )
    args = parser.parse_args()

    root = paths.require_workflow_root()
    plan = load_plan(args.plan_file)
    errors = validate_plan(
        plan,
        root,
        size_delta_threshold=args.max_size_delta,
        allow_large_delta=args.allow_large_delta,
    )

    if errors:
        output.result(
            {"plan_file": args.plan_file, "errors": errors},
            f"Plan has {len(errors)} validation error(s)",
            exit_code=1,
        )

    output.success(
        {
            "plan_file": args.plan_file,
            "spec_name": plan.get("spec_name"),
            "task_id": plan.get("task_id"),
            "file_count": len(plan.get("files") or []),
        },
        "Edit plan is valid",
    )


if __name__ == "__main__":
    cli.run_main(main)
