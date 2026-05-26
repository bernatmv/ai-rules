#!/usr/bin/env python3
"""Advance task state with session enforcement.

Atomically updates both tasks.md markers and .impl-session.json,
enforcing the per-task loop contract (no batched logging).

Usage:
  advance-task.py --target NAME --task-id ID --action start
  advance-task.py --target NAME --task-id ID --action finish --log-id UUID
  advance-task.py --target NAME --task-id ID --action start --force-start
"""
from __future__ import annotations
import _bootstrap  # noqa: F401

from sdd_core import paths, tasks, output, cli
from sdd_core.tasks import update_task_marker, MARKER_FOR_STATUS, PENDING_STATUS, IN_PROGRESS_STATUS, COMPLETED_STATUS
from sdd_core.time import ts_now
from impl.impl_session import (
    read_session,
    write_session,
    record_task_start,
    record_task_complete,
    init_session,
)

_ACTION_START = "start"
_ACTION_COMPLETE = "finish"

_MARKER_TRANSITIONS = {
    _ACTION_START: (MARKER_FOR_STATUS[PENDING_STATUS], MARKER_FOR_STATUS[IN_PROGRESS_STATUS]),
    _ACTION_COMPLETE: (MARKER_FOR_STATUS[IN_PROGRESS_STATUS], MARKER_FOR_STATUS[COMPLETED_STATUS]),
}


def _apply_marker(tasks_content: str, task_id: str, action: str) -> str:
    """Replace the checkbox marker for *task_id* using the shared helper."""
    from_marker, to_marker = _MARKER_TRANSITIONS[action]
    updated_content, was_updated = update_task_marker(
        tasks_content, task_id, from_marker, to_marker,
    )
    if not was_updated:
        expected = f"- [{from_marker}] {task_id}. ..."
        output.error(
            f"Could not find task {task_id} with expected marker for '{action}'",
            hint=f"Expected a line matching '{expected}'",
        )
    return updated_content


def _handle_start(
    args, session: dict, tasks_content: str, tasks_file, root, force_start: bool,
) -> None:
    """Handle --action start: mark task in-progress with session enforcement."""
    if not force_start:
        try:
            record_task_start(session, args.task_id)
        except ValueError as exc:
            output.error(str(exc), hint="Use --force-start to override")
    else:
        session["current_task"] = {
            "id": args.task_id,
            "status": "in_progress",
            "started_at": ts_now(),
        }

    updated_content = _apply_marker(tasks_content, args.task_id, _ACTION_START)
    tasks_file.write_text(updated_content)
    write_session(args.spec_name, session, str(root))

    output.success(
        {"taskId": args.task_id, "action": "start", "forced": force_start},
        f"Task {args.task_id} marked in-progress",
    )


def _handle_complete(
    args, session: dict, tasks_content: str, tasks_file, root,
    force_complete: bool,
) -> None:
    """Handle --action finish: mark task done with log verification."""
    if args.log_id:
        log_dir = paths.impl_logs_dir(root, args.spec_name)
        log_matches = list(log_dir.glob(f"*_{args.log_id}.md")) if log_dir.exists() else []
        if not log_matches and not force_complete:
            output.error(
                f"Log file for {args.log_id} not found on disk",
                hint=f"Expected file matching *_{args.log_id}.md in {log_dir}",
            )

    if not force_complete:
        try:
            record_task_complete(
                session, args.task_id,
                log_id=args.log_id or "forced",
                pre_existing=args.pre_existing,
            )
        except ValueError as exc:
            output.error(str(exc), hint="Use --force-complete to override")
    else:
        completed = session.get("completed_tasks") or []
        completed.append({
            "id": args.task_id,
            "logged_at": ts_now(),
            "log_id": args.log_id or "forced",
            "pre_existing": args.pre_existing,
        })
        session["completed_tasks"] = completed
        session["current_task"] = None

    updated_content = _apply_marker(tasks_content, args.task_id, _ACTION_COMPLETE)
    tasks_file.write_text(updated_content)
    write_session(args.spec_name, session, str(root))

    output.success(
        {
            "taskId": args.task_id,
            "action": _ACTION_COMPLETE,
            "logId": args.log_id,
            "forced": force_complete,
        },
        f"Task {args.task_id} marked done",
    )


def main() -> None:
    parser = cli.strict_parser(__doc__)
    cli.target_argument(parser, family="spec")
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--action", required=True, choices=[_ACTION_START, _ACTION_COMPLETE])
    parser.add_argument("--log-id", default=None,
                        type=cli.name_type("log-id"),
                        help="Log ID from log-implementation.py (required for --action finish)")
    parser.add_argument("--pre-existing", action="store_true", default=False)
    parser.add_argument("--force-start", action="store_true", default=False,
                        help="Skip session enforcement for --action start (admin recovery)")
    parser.add_argument("--force-complete", action="store_true", default=False,
                        help="Skip log-file-on-disk check for --action finish (admin recovery)")
    args = parser.parse_args()

    force_start = args.force_start
    force_complete = args.force_complete

    if args.action == _ACTION_COMPLETE and not args.log_id and not force_complete:
        output.error(
            "--log-id is required for --action finish",
            hint="Get the log_id from log-implementation.py output",
        )

    root = paths.require_workflow_root()
    tasks_file = paths.spec_dir(root, args.spec_name) / "tasks.md"
    if not tasks_file.exists():
        output.error(f"tasks.md not found for spec: {args.spec_name}")

    tasks_content = tasks_file.read_text()
    parsed = tasks.parse_tasks(tasks_content)
    task = tasks.get_task_by_id(parsed, args.task_id)
    if not task:
        output.error(f"Task '{args.task_id}' not found in spec '{args.spec_name}'")

    session = read_session(args.spec_name, str(root))
    if not session.get("spec_name"):
        session = init_session(
            spec_name=args.spec_name,
            execution_mode="standard",
            project_path=str(root),
        )

    if args.action == _ACTION_START:
        _handle_start(args, session, tasks_content, tasks_file, root, force_start)
    elif args.action == _ACTION_COMPLETE:
        _handle_complete(args, session, tasks_content, tasks_file, root, force_complete)


if __name__ == "__main__":
    cli.run_main(main)
