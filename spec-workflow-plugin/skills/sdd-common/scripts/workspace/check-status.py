#!/usr/bin/env python3
"""Check workspace coordination status and poll sub-spec progress.

Usage: .spec-workflow/sdd workspace/check-status.py --workspace <path> --target <feature> [--poll] [--verify-paths]
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

from pathlib import Path

from sdd_core import cli, handoffs, output, workspace, specs, paths, approvals
from sdd_core.workspace_tracker import is_v2

# Mirrors workflow-graph.json `sdd-workspace-create-spec.context_needs`.
__sdd_context_needs__ = ("target", "workspace")


def _verify_spec_paths(tracker: dict) -> list[dict]:
    """Validate that spec directories referenced in the tracker exist on disk.

    Returns a list of ``{"repoId", "repoPath", "subSpecName", "specDir",
    "exists"}`` entries for every sub-spec that declares a ``repoPath``.
    """
    results = []
    for sub in tracker.get("subSpecs", []):
        repo_path = sub.get("repoPath")
        sub_spec_name = sub.get("subSpecName")
        if not repo_path or not sub_spec_name:
            continue
        spec_dir = Path(repo_path) / ".spec-workflow" / "specs" / sub_spec_name
        results.append({
            "repoId": sub.get("repoId", "unknown"),
            "repoPath": repo_path,
            "subSpecName": sub_spec_name,
            "specDir": str(spec_dir),
            "exists": spec_dir.is_dir(),
        })
    return results


def main() -> None:
    parser = cli.workspace_parser("Check workspace status")
    parser.add_argument("--poll", action="store_true",
                        help="Poll live spec status from each target repo")
    parser.add_argument("--phase", help="Show status for a specific phase only")
    parser.add_argument(
        "--verify-paths", action="store_true",
        help="Validate that all spec directories in the tracker exist on disk",
    )
    args = parser.parse_args()
    ctx = cli.resolve_context(args, needs=("target", "workspace"))
    root = cli.resolve_workspace_root(args)

    tracker = workspace.require_tracker(root, args.feature)

    poll_results = []
    if args.poll:
        poll_results = workspace.poll_sub_spec_status(
            tracker.get("subSpecs", []),
            paths_module=paths,
            specs_module=specs,
            approvals_module=approvals,
        )

    manifest = workspace.read_manifest(root, args.feature)
    data = workspace.build_workspace_status(manifest, tracker, poll_results)

    if not is_v2(tracker):
        data["migrationNeeded"] = True

    if args.verify_paths:
        path_results = _verify_spec_paths(tracker)
        data["pathVerification"] = path_results
        missing = [r for r in path_results if not r["exists"]]
        if missing:
            names = ", ".join(r["repoId"] for r in missing)
            data.setdefault("advisories", []).append(
                {"name": "missing-spec-dirs", "level": "warn",
                 "message": f"Spec directories missing for: {names}"}
            )

    if args.phase:
        phase_progress = workspace.phase_progress_summary(
            tracker, args.phase,
        )
        needs_work = [
            s.get("repoId", "?")
            for s in workspace.repos_needing_work(tracker, args.phase)
        ]
        data["requestedPhase"] = args.phase
        data["phaseProgress"] = phase_progress
        data["needsWork"] = needs_work

    summary = tracker.get("summary", {})
    total = summary.get("totalSubSpecs", 0)
    completed = summary.get("completed", 0)
    approved = summary.get("approvedSubSpecs", 0)
    current_phase = tracker.get("currentPhase", "N/A")

    msg = f"Workspace {args.feature}: {completed}/{total} completed, {approved}/{total} approved"
    if current_phase != "N/A":
        msg += f", phase: {current_phase}"

    output.success(
        data,
        msg,
        ctx=ctx,
        resolved_from=dict(ctx.resolved_from),
        handoffs=handoffs.handoffs_for(handoffs.current_script_id(), ctx),
    )


if __name__ == "__main__":
    cli.run_main(main)
