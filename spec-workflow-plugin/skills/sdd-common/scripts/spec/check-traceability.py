#!/usr/bin/env python3
"""Validate requirements traceability between requirements.md and tasks.md.

Usage:
  check-traceability.py <requirements.md> <tasks.md>
  check-traceability.py --target <spec-name>
Exit code: 0 if full coverage, 1 if gaps found, 2 on usage error.
"""

from __future__ import annotations

import _bootstrap  # noqa: F401

import json

from sdd_core import cli, handoffs, output
from sdd_core.traceability import (
    analyse_traceability,
    extract_requirement_ids,
    is_bug_fix_content,
)
from skill_helpers import safe_open

# Mirrors workflow-graph.json `sdd-create-spec.context_needs`.
__sdd_context_needs__ = ("target", "workspace")

_MULTI_TARGET_PASS_MSG = "FULL COVERAGE across {n} target(s)"
_MULTI_TARGET_GAPS_MSG = (
    "GAPS FOUND in {n_failed} of {n_total} target(s): {names}"
)


def _read(path: str) -> str:
    with safe_open(path) as f:
        return f.read()


def _check_one(spec_name: str) -> dict:
    """Run the traceability check for *spec_name* under the canonical layout.

    Returns a per-target sub-result envelope with ``valid`` plus the
    raw :class:`TraceabilityResult` fields, suitable for inclusion in
    ``data.targets[]``.
    """
    req_file = f".spec-workflow/specs/{spec_name}/requirements.md"
    tasks_file = f".spec-workflow/specs/{spec_name}/tasks.md"
    req_content = _read(req_file)
    tasks_content = _read(tasks_file)
    if not extract_requirement_ids(req_content) and is_bug_fix_content(req_content):
        return {
            "target": spec_name,
            "valid": True,
            "result": "not_applicable",
            "reason": "bug-fix spec",
        }
    result = analyse_traceability(req_content, tasks_content)
    payload: dict = {"target": spec_name, "valid": result["result"] != "gaps_found"}
    payload.update(dict(result))
    return payload


def main() -> None:
    parser = cli.strict_parser(
        "Validate requirements traceability between requirements.md and tasks.md",
    )
    parser.add_argument("requirements_file", nargs="?", default=None, help="Path to requirements.md")
    parser.add_argument("tasks_file", nargs="?", default=None, help="Path to tasks.md")
    cli.target_argument(parser, family="spec", required=False)
    parser.add_argument(
        "--targets", nargs="+", default=None,
        help=(
            "Repeatable: process each spec name independently and emit "
            "per-target sub-results under ``data.targets[]``. Mutually "
            "exclusive with positional ``<req.md> <tasks.md>``; coexists "
            "with single-target ``--target`` (which is kept for back "
            "compatibility — agents migrating to multi-target should "
            "switch to ``--targets``)."
        ),
    )
    args = parser.parse_args()
    ctx = cli.resolve_context(args, needs=__sdd_context_needs__)

    targets: list[str] = list(args.targets or [])

    def _emit(payload: dict, msg: str) -> None:
        output.success(
            payload,
            msg,
            ctx=ctx,
            resolved_from=dict(ctx.resolved_from),
            handoffs=handoffs.handoffs_for(handoffs.current_script_id(), ctx),
        )

    if targets and not args.requirements_file:
        sub_results = [_check_one(t) for t in targets]
        all_valid = all(s.get("valid") for s in sub_results)
        envelope = {
            "valid": all_valid,
            "targets": sub_results,
        }
        if all_valid:
            _emit(envelope, _MULTI_TARGET_PASS_MSG.format(n=len(sub_results)))
            return
        gap_targets = [s["target"] for s in sub_results if not s.get("valid")]
        output.error(
            _MULTI_TARGET_GAPS_MSG.format(
                n_failed=len(gap_targets),
                n_total=len(sub_results),
                names=", ".join(gap_targets),
            ),
            context=json.dumps(envelope, indent=2),
        )
        return

    req_file = args.requirements_file
    tasks_file = args.tasks_file
    if args.spec_name and not req_file:
        req_file = f".spec-workflow/specs/{args.spec_name}/requirements.md"
        tasks_file = tasks_file or f".spec-workflow/specs/{args.spec_name}/tasks.md"
    if not req_file or not tasks_file:
        output.error(
            "Either positional args, --target, or --targets is required",
            hint="Usage: check-traceability.py <req.md> <tasks.md> or --target <spec-name> or --targets <name>...",
        )

    req_content = _read(req_file)
    tasks_content = _read(tasks_file)

    if not extract_requirement_ids(req_content) and is_bug_fix_content(req_content):
        _emit(
            {"result": "not_applicable", "reason": "bug-fix spec"},
            "Bug-fix spec detected — traceability check not applicable",
        )

    result = analyse_traceability(req_content, tasks_content)
    has_gap = result["result"] == "gaps_found"

    if has_gap:
        parts: list[str] = []
        if result["missing"]:
            parts.append(
                f"{len(result['missing'])} uncovered requirement(s): "
                f"{', '.join(result['missing'])}"
            )
        if result["orphanRefs"]:
            parts.append(
                f"{len(result['orphanRefs'])} orphan ref(s): "
                f"{', '.join(result['orphanRefs'])} "
                f"(non-numeric tokens are not accepted — see "
                f"$SKILLS/sdd-common/references/task-validation-rules.md "
                f"§ _Requirements: Format)"
            )
        output.error(f"GAPS FOUND: {'; '.join(parts)}")
    else:
        _emit(dict(result), "FULL COVERAGE")


if __name__ == "__main__":
    cli.run_main(main)
