#!/usr/bin/env python3
"""Batch-approve workspace sub-specs in a single pass.

.. deprecated:: v2.0.0
   Legacy v1-vertical-only script. For v2 batch-by-doc-type workspaces,
   use ``phase-approve.py`` instead.

Usage:
  .spec-workflow/sdd workspace/batch-approve.py --workspace <path> --target <feature> [--dry-run]

Displays a summary of pending sub-specs and returns requiresConfirmation: true.
The agent must call confirm-batch-approval.py after receiving user consent.

To prevent race conditions, writes a pending-approval-batch.json file listing
the exact repo IDs shown to the user. confirm-batch-approval.py reads this file
instead of re-scanning, ensuring confirmation applies to what was presented.

For phase-aware approval (single doc type), use phase-approve.py instead.
"""
import _bootstrap  # noqa: F401

from sdd_core import cli, handoffs, output, workspace
from sdd_core.workspace_tracker import is_v2

# Mirrors workflow-graph.json `sdd-workspace-create-spec.context_needs`.
__sdd_context_needs__ = ("target", "workspace")


def main() -> None:
    parser = cli.workspace_parser("Batch approve workspace sub-specs")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview pending sub-specs without writing the batch file",
    )
    args = parser.parse_args()
    ctx = cli.resolve_context(args, needs=("target", "workspace"))
    root = cli.resolve_workspace_root(args)

    manifest = workspace.require_manifest(root, args.feature)
    tracker = workspace.require_tracker(
        root, args.feature, hint="Run update-tracker.py to initialise the tracker",
    )

    batch_advisories: list[dict] = []
    if is_v2(tracker):
        batch_advisories.append({
            "name": "batch-approve-deprecated",
            "level": "warn",
            "message": (
                "This script is deprecated for v2.0.0+ workspaces. "
                "Use workspace/phase-approve.py instead."
            ),
        })

    pending = workspace.require_pending_subspecs(tracker, args.feature, "spec_created")

    if not pending:
        no_pending_data: dict = {"feature": args.feature, "approved": [], "message": "Nothing to approve"}
        if batch_advisories:
            no_pending_data["advisories"] = batch_advisories
        output.success(
            no_pending_data,
            "No sub-specs at 'spec_created' status",
            ctx=ctx,
            resolved_from=dict(ctx.resolved_from),
        )
        return

    summary_text = workspace.generate_approval_summary(manifest, tracker, pending)

    pending_repo_ids = [s.get("repoId") for s in pending]

    if args.dry_run:
        dry_batch: dict = {"dryRun": True, "feature": args.feature, "summary": summary_text,
             "pendingCount": len(pending), "pendingRepoIds": pending_repo_ids}
        if batch_advisories:
            dry_batch["advisories"] = batch_advisories
        output.success(
            dry_batch,
            f"[dry-run] Would prepare batch approval for {len(pending)} sub-spec(s): {pending_repo_ids}",
            ctx=ctx,
            resolved_from=dict(ctx.resolved_from),
        )
        return

    workspace.create_pending_batch(root, args.feature, "approval", pending_repo_ids)

    data: dict = {
        "feature": args.feature,
        "summary": summary_text,
        "requiresConfirmation": True,
        "pendingCount": len(pending),
        "pendingRepoIds": pending_repo_ids,
    }
    if batch_advisories:
        data["advisories"] = batch_advisories
    output.success(
        data,
        f"Review summary above. Confirm to batch-approve {len(pending)} sub-spec(s).",
        ctx=ctx,
        resolved_from=dict(ctx.resolved_from),
        handoffs=handoffs.handoffs_for(handoffs.current_script_id(), ctx),
    )


if __name__ == "__main__":
    cli.run_main(main)
