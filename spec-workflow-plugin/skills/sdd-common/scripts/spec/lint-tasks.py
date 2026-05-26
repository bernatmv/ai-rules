#!/usr/bin/env python3
"""Validate tasks.md: prompt structure + lifecycle suffix (file-level).

Thin CLI wrapper around sdd_core.task_validation.

Usage:
  lint-tasks.py <tasks.md>
  lint-tasks.py --target <spec-name>

Exit codes: see `script-conventions.md` § Exit Codes — canonical policy
(0 = success, 1 = user error or validation failure, 2 = system error).
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

from skill_helpers import safe_open
from sdd_core import cli, handoffs, output
from sdd_core import tasks as tasks_module
from sdd_core.task_validation import validate
from sdd_core.tasks import is_header, COMPLETED_STATUS

# Mirrors workflow-graph.json `sdd-create-spec.context_needs`.
__sdd_context_needs__ = ("target", "workspace")

_MULTI_TARGET_PASS_MSG = "PASS across {n} target(s)"
_MULTI_TARGET_PARTIAL_MSG = (
    "PARTIAL: {n_failed} of {n_total} target(s) failed"
)


def _lint_one(spec_name: str, ctx) -> dict:
    """Run lint-tasks against the canonical tasks.md for *spec_name*.

    Returns a per-target sub-result envelope: ``{target, valid,
    passed, failed, skipped, skipped_headers, tasks_file}``.
    """
    tasks_file = f".spec-workflow/specs/{spec_name}/tasks.md"
    with safe_open(tasks_file) as f:
        content = f.read()
    parsed = tasks_module.parse_tasks(content)
    result = validate(parsed, content)
    passed = failed = skipped = skipped_headers = 0
    for task in parsed:
        if task["status"] == COMPLETED_STATUS:
            skipped += 1
            continue
        if is_header(task):
            skipped_headers += 1
            continue
        task_issues = [
            e for e in result["errors"] + result["warnings"]
            if e.get("task") == task["id"]
        ]
        if task_issues:
            failed += 1
        else:
            passed += 1
    return {
        "target": spec_name,
        "valid": failed == 0,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "skipped_headers": skipped_headers,
        "tasks_file": tasks_file,
    }


def main() -> None:
    parser = cli.strict_parser(__doc__)
    parser.add_argument("tasks_file", nargs="?", default=None,
                        help="Path to tasks.md")
    cli.target_argument(parser, family="spec", required=False)
    parser.add_argument(
        "--targets", nargs="+", default=None,
        help=(
            "Repeatable: process each spec name independently and emit "
            "per-target sub-results under ``data.targets[]``. Coexists "
            "with single-target ``--target`` for back compatibility."
        ),
    )
    args = parser.parse_args()
    ctx = cli.resolve_context(args, needs=__sdd_context_needs__)

    targets: list[str] = list(args.targets or [])
    if targets and not args.tasks_file:
        sub_results = [_lint_one(t, ctx) for t in targets]
        all_valid = all(s.get("valid") for s in sub_results)
        envelope = {"valid": all_valid, "targets": sub_results}
        if all_valid:
            output.success(
                envelope,
                _MULTI_TARGET_PASS_MSG.format(n=len(sub_results)),
                ctx=ctx,
                resolved_from=dict(ctx.resolved_from),
                handoffs=handoffs.handoffs_for(handoffs.current_script_id(), ctx),
            )
            return
        output.partial(
            envelope,
            _MULTI_TARGET_PARTIAL_MSG.format(
                n_failed=sum(1 for s in sub_results if not s.get("valid")),
                n_total=len(sub_results),
            ),
        )
        return

    tasks_file = args.tasks_file
    if not tasks_file and getattr(args, "spec_name", None):
        tasks_file = f".spec-workflow/specs/{args.spec_name}/tasks.md"
    if not tasks_file:
        output.error(
            "Either <tasks_file>, --target <spec-name>, or --targets <name>... is required",
            hint="Usage: lint-tasks.py <path> or lint-tasks.py --target <name> or lint-tasks.py --targets <name>...",
        )

    with safe_open(tasks_file) as f:
        content = f.read()
    tasks = tasks_module.parse_tasks(content)
    result = validate(tasks, content)

    passed = failed = skipped = skipped_headers = 0
    for task in tasks:
        if task["status"] == COMPLETED_STATUS:
            skipped += 1
            continue
        if is_header(task):
            skipped_headers += 1
            output.info(f"  SKIP  task {task['id']}: header (no validation needed)")
            continue
        task_issues = [
            e for e in result["errors"] + result["warnings"]
            if e.get("task") == task["id"]
        ]
        if task_issues:
            failed += 1
            for issue in task_issues:
                output.info(f"  FAIL  task {task['id']}: {issue['message']}")
        else:
            passed += 1
            output.info(f"  PASS  task {task['id']}")

    total_skipped = skipped + skipped_headers
    skip_detail = f"{skipped} complete"
    if skipped_headers:
        skip_detail += f", {skipped_headers} headers"
    output.info(f"\nSummary: {passed} passed, {failed} failed, {total_skipped} skipped ({skip_detail})")

    if failed == 0:
        output.success(
            {"result": "pass", "passed": passed, "failed": 0, "skipped": skipped,
             "skipped_headers": skipped_headers},
            f"PASS {tasks_file} ({passed} tasks valid, {skipped_headers} headers skipped)",
            ctx=ctx,
            resolved_from=dict(ctx.resolved_from),
            handoffs=handoffs.handoffs_for(handoffs.current_script_id(), ctx),
        )
    else:
        output.partial(
            {
                "result": "partial", "passed": passed, "failed": failed,
                "skipped": skipped, "skipped_headers": skipped_headers,
                "tasks_file": tasks_file,
            },
            f"PARTIAL {tasks_file} ({failed} of {passed + failed} tasks invalid)",
        )


if __name__ == "__main__":
    cli.run_main(main)
