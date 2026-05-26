#!/usr/bin/env python3
"""Confirm and execute a batch approval for workspace sub-specs.

.. deprecated:: v2.0.0
   Legacy v1-vertical-only script. For v2 batch-by-doc-type workspaces,
   use ``phase-approve.py`` instead.

Called after batch-approve.py presents the summary and the user confirms.
Reads pending-approval-batch.json written by batch-approve.py to ensure it
approves exactly the same repos that were presented — not a fresh scan that
could differ if the tracker changed between the two calls.

Usage: .spec-workflow/sdd workspace/confirm-batch-approval.py --workspace <path> --target <feature>
"""
import _bootstrap  # noqa: F401

from sdd_core import cli, handoffs, output, workspace
from sdd_core.workspace_tracker import is_v2

# Mirrors workflow-graph.json `sdd-workspace-create-spec.context_needs`.
__sdd_context_needs__ = ("target", "workspace")


def main() -> None:
    parser = cli.workspace_parser("Confirm batch approval")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview changes without writing to disk",
    )
    args = parser.parse_args()
    ctx = cli.resolve_context(args, needs=("target", "workspace"))
    root = cli.resolve_workspace_root(args)

    tracker = workspace.require_tracker(
        root, args.feature, hint="Run batch-approve.py first",
    )

    confirm_advisories: list[dict] = []
    if is_v2(tracker):
        confirm_advisories.append({
            "name": "confirm-batch-deprecated",
            "level": "warn",
            "message": (
                "This script is deprecated for v2.0.0+ workspaces. "
                "Use workspace/phase-approve.py instead."
            ),
        })

    try:
        repo_ids = workspace.read_pending_batch(root, args.feature, "approval")
        pending = [s for s in tracker.get("subSpecs", []) if s.get("repoId") in repo_ids]
    except FileNotFoundError:
        pending = workspace.collect_pending_subspecs(tracker, "spec_created")

    if not pending:
        no_pending: dict = {"feature": args.feature, "approved": []}
        if confirm_advisories:
            no_pending["advisories"] = confirm_advisories
        output.success(
            no_pending,
            "No sub-specs to confirm — nothing to approve",
            ctx=ctx,
            resolved_from=dict(ctx.resolved_from),
        )
        return

    if args.dry_run:
        repo_ids = [s.get("repoId") for s in pending]
        dry_confirm: dict = {"dryRun": True, "feature": args.feature, "wouldApprove": repo_ids}
        if confirm_advisories:
            dry_confirm["advisories"] = confirm_advisories
        output.success(
            dry_confirm,
            f"[dry-run] Would batch-approve {len(pending)} sub-spec(s): {repo_ids}",
            ctx=ctx,
            resolved_from=dict(ctx.resolved_from),
        )
        return

    result = workspace.apply_batch_approval(root, args.feature, pending)

    workspace.cleanup_pending_batch(root, args.feature, "approval")

    approved_count = len(result["approved"])
    failed_count = len(result["failed"])
    confirm_result: dict = {"feature": args.feature, "result": result}
    if confirm_advisories:
        confirm_result["advisories"] = confirm_advisories
    output.success(
        confirm_result,
        f"Batch approved {approved_count} sub-spec(s), {failed_count} failed",
        ctx=ctx,
        resolved_from=dict(ctx.resolved_from),
        handoffs=handoffs.handoffs_for(handoffs.current_script_id(), ctx),
    )


if __name__ == "__main__":
    cli.run_main(main)
