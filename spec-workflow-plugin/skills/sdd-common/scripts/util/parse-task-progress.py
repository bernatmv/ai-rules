#!/usr/bin/env python3
"""Parse task progress from tasks.md.

Usage: parse-task-progress.py --tasks-file PATH
"""
import _bootstrap  # noqa: F401

import os

from sdd_core import tasks, output, cli

def main():
    parser = cli.strict_parser("Parse task progress")
    parser.add_argument("--tasks-file", required=True)
    args = parser.parse_args()

    if not os.path.isfile(args.tasks_file):
        output.error(f"File not found: {args.tasks_file}")

    with open(args.tasks_file) as f:
        content = f.read()

    parsed = tasks.parse_tasks(content)
    progress = tasks.calculate_progress(parsed)

    task_list = []
    for t in parsed:
        task_list.append({"id": t["id"], "description": t["description"], "status": t["status"]})

    output.success({**progress, "tasks": task_list}, f"{progress['completed']}/{progress['total']} tasks completed")

if __name__ == "__main__":
    cli.run_main(main)
