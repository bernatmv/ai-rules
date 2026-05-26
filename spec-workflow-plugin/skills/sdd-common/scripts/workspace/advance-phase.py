#!/usr/bin/env python3
"""Advance workspace to the next document phase.

Validates all active repos are approved/skipped for the current phase,
records a phase gate, then advances ``currentPhase`` to the next phase.

Usage: .spec-workflow/sdd workspace/advance-phase.py --target <feature> [--workspace PATH] [--dry-run]

``apply_phase_approval`` already records the phase
gate and bumps ``currentPhase`` atomically when the last repo's
approval lands. This shim remains the canonical entry point for v1.1.0
trackers (where the atomic write was not yet in place) and for the
Resume Protocol fallback. It is idempotent: returns success without
re-writing when the phase is already advanced.
"""
import _bootstrap  # noqa: F401

from sdd_core import cli, handoffs, output, workspace
from sdd_core.workspace_phase import PHASE_COMPLETE, advance_with_gate

# Mirrors workflow-graph.json `sdd-workspace-create-spec.context_needs`.
__sdd_context_needs__ = ("target", "workspace", "phase")


def main() -> None:
    parser = cli.strict_parser("Advance workspace to next phase")
    cli.add_workspace_arg(parser)
    cli.target_argument(parser, family="workspace")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview the transition without writing to disk",
    )
    args = parser.parse_args()
    ctx = cli.resolve_context(args, needs=("target", "workspace", "phase"))
    root = cli.resolve_workspace_root(args)
    feature = args.feature

    tracker = workspace.require_tracker(
        root, feature, hint="Run update-tracker.py to initialise the tracker",
    )

    current = workspace.get_current_phase(tracker)
    if current is None:
        output.error(
            "currentPhase is not set",
            hint="Set currentPhase via update-tracker.py or start Phase R first",
        )

    # Idempotent re-entry: when ``apply_phase_approval`` already advanced
    # the tracker, scanning ``phaseGates`` for the most-recently sealed
    # entry whose successor matches ``currentPhase`` lets us return a
    # success envelope instead of erroring with a stale "phase not
    # complete" message.
    phase_gates = tracker.get("phaseGates") or {}
    previous_phase = next(
        (
            prev for prev, succ in workspace.PHASE_ORDER.items()
            if (
                (succ if succ is not None else PHASE_COMPLETE) == current
                and phase_gates.get(prev) is not None
            )
        ),
        None,
    )
    if previous_phase is not None:
        output.success(
            {
                "feature": feature,
                "alreadyAdvanced": True,
                "previousPhase": previous_phase,
                "currentPhase": current,
                "phaseGate": phase_gates.get(previous_phase),
            },
            (
                f"Already at '{current}' — apply_phase_approval already "
                f"advanced from '{previous_phase}'."
            ),
            ctx=ctx,
            resolved_from=dict(ctx.resolved_from),
            handoffs=handoffs.handoffs_for(handoffs.current_script_id(), ctx),
        )
        return

    if args.dry_run:
        complete = workspace.is_phase_complete(tracker, current)
        next_phase = workspace.PHASE_ORDER.get(current)
        output.success(
            {
                "dryRun": True,
                "currentPhase": current,
                "isComplete": complete,
                "nextPhase": next_phase or PHASE_COMPLETE,
            },
            f"[dry-run] Phase '{current}' complete={complete}, "
            f"next='{next_phase or PHASE_COMPLETE}'",
            ctx=ctx,
            resolved_from=dict(ctx.resolved_from),
        )
        return

    new_phase = advance_with_gate(tracker, current)
    if new_phase is None:
        output.error(
            f"Cannot advance from '{current}': "
            f"not all active repos are approved/skipped",
        )

    workspace.finalize_and_save(root, feature, tracker)

    output.success(
        {
            "feature": feature,
            "previousPhase": current,
            "currentPhase": new_phase,
            "phaseGate": tracker.get("phaseGates", {}).get(current),
        },
        f"Advanced from '{current}' to '{new_phase}'",
        ctx=ctx,
        resolved_from=dict(ctx.resolved_from),
        handoffs=handoffs.handoffs_for(handoffs.current_script_id(), ctx),
    )


if __name__ == "__main__":
    cli.run_main(main)
