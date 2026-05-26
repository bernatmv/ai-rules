#!/usr/bin/env python3
"""Reconcile workspace tracker — recalculate summary and byPhase from subSpecs state.

Usage: .spec-workflow/sdd workspace/reconcile-tracker.py --workspace <path> --target <feature> [--dry-run]

Idempotent: safe to run at any time. Only mutates the summary block and
updatedAt timestamp; never touches subSpecs[], docStatus, or approvals.
"""
import _bootstrap  # noqa: F401

from sdd_core import cli, handoffs, output, workspace

# Mirrors workflow-graph.json `sdd-workspace-create-spec.context_needs`.
__sdd_context_needs__ = ("target", "workspace")


def main() -> None:
    parser = cli.workspace_parser(
        "Reconcile tracker summary from subSpecs state (idempotent)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview reconciled summary without writing to disk",
    )
    args = parser.parse_args()
    ctx = cli.resolve_context(args, needs=("target", "workspace"))

    root = cli.resolve_workspace_root(args)
    tracker = workspace.require_tracker(
        root, args.feature, hint="No tracker found to reconcile",
    )

    old_summary = tracker.get("summary", {})
    new_summary = workspace.calculate_summary(tracker)

    changed_keys = [
        k for k in sorted(set(list(old_summary.keys()) + list(new_summary.keys())))
        if old_summary.get(k) != new_summary.get(k)
    ]

    if not changed_keys:
        output.success(
            {"feature": args.feature, "changed": False},
            "Tracker summary already consistent — no changes needed",
            ctx=ctx,
            resolved_from=dict(ctx.resolved_from),
        )
        return

    if args.dry_run:
        diff = {k: {"old": old_summary.get(k), "new": new_summary.get(k)} for k in changed_keys}
        output.success(
            {"dryRun": True, "feature": args.feature, "diff": diff},
            f"[dry-run] Would update {len(changed_keys)} summary field(s)",
            ctx=ctx,
            resolved_from=dict(ctx.resolved_from),
        )
        return

    workspace.finalize_and_save(root, args.feature, tracker)
    output.success(
        {"feature": args.feature, "changed": True, "updatedKeys": changed_keys},
        f"Reconciled {len(changed_keys)} summary field(s)",
        ctx=ctx,
        resolved_from=dict(ctx.resolved_from),
        handoffs=handoffs.handoffs_for(handoffs.current_script_id(), ctx),
    )


if __name__ == "__main__":
    cli.run_main(main)
