#!/usr/bin/env python3
"""Show per-repo docStatus for the current (or specified) phase.

Usage: .spec-workflow/sdd workspace/phase-status.py --workspace <path> --target <feature> [--phase <name>]
"""
import _bootstrap  # noqa: F401

from sdd_core import cli, handoffs, output, workspace
from sdd_core.workspace_phase import DOC_PHASES, PHASE_COMPLETE

# Mirrors workflow-graph.json `sdd-workspace-create-spec.context_needs`.
__sdd_context_needs__ = ("target", "workspace", "phase")


def main() -> None:
    parser = cli.workspace_parser("Show phase-level workspace status")
    parser.add_argument(
        "--phase", choices=list(DOC_PHASES),
        help="Specific phase to show (defaults to currentPhase)",
    )
    args = parser.parse_args()
    ctx = cli.resolve_context(args, needs=("target", "workspace", "phase"))
    root = cli.resolve_workspace_root(args)

    tracker = workspace.require_tracker(root, args.feature)

    current_phase = workspace.get_current_phase(tracker)
    target_phase = args.phase or current_phase

    if target_phase is None:
        output.error(
            "No current phase detected",
            hint="Specify --phase explicitly or set currentPhase in the tracker",
        )

    phases_to_show = (
        [target_phase] if target_phase != PHASE_COMPLETE
        else list(workspace.DOC_PHASES)
    )

    phase_data = {}
    for phase in phases_to_show:
        per_repo = []
        for sub in tracker.get("subSpecs", []):
            doc_status = sub.get("docStatus", {}).get(phase, "pending")
            per_repo.append({
                "repoId": sub.get("repoId", "?"),
                "docStatus": doc_status,
            })
        phase_data[phase] = {
            "repos": per_repo,
            "complete": workspace.is_phase_complete(tracker, phase),
            "progress": workspace.phase_progress_summary(tracker, phase),
        }

    needs_work = []
    if target_phase and target_phase != PHASE_COMPLETE:
        needs_work = [
            s.get("repoId", "?")
            for s in workspace.repos_needing_work(tracker, target_phase)
        ]

    data = {
        "feature": args.feature,
        "currentPhase": current_phase,
        "requestedPhase": target_phase,
        "phases": phase_data,
        "needsWork": needs_work,
        "phaseGates": tracker.get("phaseGates", {}),
    }

    if needs_work:
        msg = (
            f"Phase '{target_phase}': "
            f"{len(needs_work)} repo(s) need work: {needs_work}"
        )
    else:
        msg = f"Phase '{target_phase}': all repos complete"

    output.success(
        data,
        msg,
        ctx=ctx,
        resolved_from=dict(ctx.resolved_from),
        handoffs=handoffs.handoffs_for(handoffs.current_script_id(), ctx),
    )


if __name__ == "__main__":
    cli.run_main(main)
