#!/usr/bin/env python3
"""Emit an ``edit-plan.json`` scaffold for a multi-file implementation task.

Part of the plan-validate-execute pipeline — used by
``sdd-implement-spec`` when a task touches more than five files to
surface scope and out-of-tree edits before any bytes are written.

Usage:
    plan-task.py --target NAME --task-id ID \
        [--file PATH[:ACTION][:DELTA]]... \
        [--acceptance "criterion"]... \
        [--out plan.json]

When ``--out`` is omitted the plan is printed in the JSON ``data``
envelope, which the calling agent can pipe into
``impl/validate-plan.py`` without intermediate storage.

Hints parsed from tasks.md:
    If the selected task has ``_Files:`` or ``Files:`` metadata, those
    paths are added automatically with ``action=modify``. Acceptance
    criteria are pre-populated from the ``_Requirements:`` field when
    present. The user can still add ``--file`` / ``--acceptance``.
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

from pathlib import Path

from sdd_core import cli, output, paths, tasks
from sdd_core.edit_plans import (
    DEFAULT_FILE_THRESHOLD,
    build_plan,
    requires_plan,
    save_plan,
)


def _parse_file_spec(spec: str) -> dict:
    """Accept ``path``, ``path:action``, or ``path:action:delta`` forms."""
    parts = spec.split(":", 2)
    entry: dict = {"path": parts[0].strip(), "action": "modify"}
    if len(parts) >= 2 and parts[1]:
        entry["action"] = parts[1].strip()
    if len(parts) >= 3 and parts[2]:
        try:
            entry["size_delta_estimate"] = int(parts[2].strip())
        except ValueError:
            output.error(
                f"Invalid size delta in --file spec: {spec!r}",
                hint="Expected integer number of lines",
            )
    return entry


def _metadata_files(task: dict) -> list[dict]:
    """Extract file hints from ``_Files:`` / ``Files:`` metadata lines."""
    meta = task.get("metadata", {}) or {}
    raw = meta.get("Files") or meta.get("File") or ""
    if not raw:
        return []
    return [
        {"path": p.strip(), "action": "modify", "summary": "from task metadata"}
        for p in raw.split(",")
        if p.strip()
    ]


def _metadata_acceptance(task: dict) -> list[str]:
    meta = task.get("metadata", {}) or {}
    raw = meta.get("Requirements") or ""
    if not raw:
        return []
    return [f"Satisfies requirement {r.strip()}" for r in raw.split(",") if r.strip()]


def main() -> None:
    parser = cli.strict_parser("Emit an edit-plan.json scaffold for a spec task")
    cli.target_argument(parser, family="spec")
    parser.add_argument("--task-id", required=True)
    parser.add_argument(
        "--file",
        action="append",
        default=[],
        metavar="PATH[:ACTION][:DELTA]",
        help="Add a file entry (repeatable). Action defaults to 'modify'.",
    )
    parser.add_argument(
        "--acceptance",
        action="append",
        default=[],
        help="Add an acceptance-criteria string (repeatable)",
    )
    parser.add_argument("--out", help="Write plan JSON to this path")
    parser.add_argument(
        "--threshold",
        type=int,
        default=DEFAULT_FILE_THRESHOLD,
        help=(
            f"File-count threshold above which a plan is required "
            f"(default {DEFAULT_FILE_THRESHOLD})"
        ),
    )
    args = parser.parse_args()

    root = paths.require_workflow_root()
    tasks_file = paths.spec_dir(root, args.spec_name) / "tasks.md"
    if not tasks_file.exists():
        output.error(f"tasks.md not found for spec: {args.spec_name}")

    parsed = tasks.parse_tasks(tasks_file.read_text())
    task = tasks.get_task_by_id(parsed, args.task_id)
    if task is None:
        output.error(f"Task '{args.task_id}' not found in spec '{args.spec_name}'")

    files: list[dict] = _metadata_files(task)
    for spec in args.file:
        files.append(_parse_file_spec(spec))

    acceptance: list[str] = _metadata_acceptance(task)
    acceptance.extend(args.acceptance)

    plan = build_plan(
        spec_name=args.spec_name,
        task_id=args.task_id,
        files=files,
        acceptance_criteria=acceptance,
    )

    advisory = {
        "file_count": len(files),
        "plan_required": requires_plan(len(files), threshold=args.threshold),
        "threshold": args.threshold,
    }

    if args.out:
        out_path = Path(args.out)
        if not out_path.is_absolute():
            out_path = Path.cwd() / out_path
        save_plan(out_path, plan)
        output.success(
            {"plan_path": str(out_path), "plan": plan, **advisory},
            f"Wrote edit plan to {out_path}",
        )

    output.success(
        {"plan": plan, **advisory},
        f"Edit plan scaffold for task {args.task_id} ({len(files)} file(s))",
    )


if __name__ == "__main__":
    cli.run_main(main)
