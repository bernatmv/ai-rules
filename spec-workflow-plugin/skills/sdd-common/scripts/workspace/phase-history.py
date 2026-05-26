#!/usr/bin/env python3
"""Read-only audit trail of ``currentPhase`` advancements.

Usage:
  .spec-workflow/sdd workspace/phase-history.py --target <feature> [--phase <name>] [--workspace PATH]

Emits the ``phaseHistory`` slice from the workspace tracker, optionally
filtered to a single phase.
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

from sdd_core import cli, handoffs, output, workspace
from sdd_core.workspace_phase import PHASE_ORDER

# Mirrors workflow-graph.json `sdd-workspace-create-spec.context_needs`.
__sdd_context_needs__ = ("target", "workspace")

_PHASE_HISTORY_KEY = "phaseHistory"
_CURRENT_PHASE_KEY = "currentPhase"


def main() -> None:
    parser = cli.workspace_parser("Read currentPhase advancement history")
    parser.add_argument(
        "--phase",
        choices=tuple(PHASE_ORDER.keys()),
        help="Filter history to a single phase",
    )
    args = parser.parse_args()
    ctx = cli.resolve_context(args, needs=("target", "workspace"))
    root = cli.resolve_workspace_root(args)

    tracker = workspace.require_tracker(root, args.feature)
    history = list(tracker.get(_PHASE_HISTORY_KEY) or [])
    if args.phase:
        history = [e for e in history if e.get("phase") == args.phase]

    output.success(
        {
            "feature": args.feature,
            _CURRENT_PHASE_KEY: tracker.get(_CURRENT_PHASE_KEY),
            _PHASE_HISTORY_KEY: history,
        },
        f"phaseHistory entries: {len(history)}",
        ctx=ctx,
        resolved_from=dict(ctx.resolved_from),
        handoffs=handoffs.handoffs_for(handoffs.current_script_id(), ctx),
    )


if __name__ == "__main__":
    cli.run_main(main)
