#!/usr/bin/env python3
"""Record a doc-level approval for coordination or a sub-spec repo.

Usage:
  .spec-workflow/sdd workspace/set-doc-approval.py
    --workspace <path> --target <feature>
    --repo-target <coordination|repo-id>
    --doc <requirements|design|tasks> --approval-status <status>
    [--approval-id <id>]
"""
import _bootstrap  # noqa: F401

from sdd_core import cli, handoffs, output, workspace
from sdd_core import time as sdd_time
from sdd_core.workspace_phase import DOC_PHASES
from sdd_core.workspace_tracker import is_v2
from sdd_core.workspace_manifest import get_coordinator

# Mirrors workflow-graph.json `sdd-workspace-create-spec.context_needs`.
__sdd_context_needs__ = ("target", "workspace")

_DOC_HELP = "Document type: " + ", ".join(DOC_PHASES)


def main() -> None:
    parser = cli.workspace_parser(
        "Record a doc-level approval in the workspace tracker",
    )
    # ``--target`` (registered by ``workspace_parser``) carries the
    # workflow feature; ``--repo-target`` carries the doc-approval scope
    # (``coordination`` vs a specific repo-id).
    parser.add_argument(
        "--repo-target", dest="repo_target", required=True,
        help="'coordination' or repo-id",
    )
    parser.add_argument(
        "--doc", required=True, choices=list(DOC_PHASES), help=_DOC_HELP,
    )
    parser.add_argument("--approval-id", type=cli.name_type("approval-id"),
                        help="Approval artifact ID")
    parser.add_argument("--approval-status", required=True, help="Approval status to set")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview changes without writing to disk",
    )

    args = parser.parse_args()
    ctx = cli.resolve_context(args, needs=("target", "workspace"))

    root = cli.resolve_workspace_root(args)
    tracker = workspace.read_tracker(root, args.feature)
    if not tracker:
        tracker = workspace.create_default_tracker(args.feature)

    set_doc_advisories: list[dict] = []
    if args.repo_target == "coordination" and is_v2(tracker):
        manifest = workspace.require_manifest(root, args.feature)
        coord = get_coordinator(manifest)
        if coord.get("id"):
            set_doc_advisories.append({
                "name": "coordination-deprecated",
                "level": "warn",
                "message": (
                    "--repo-target coordination is deprecated in v2.0.0+. "
                    f"Resolving to --repo-target {coord['id']}"
                ),
            })
            args.repo_target = coord["id"]

    try:
        workspace.update_doc_approval(
            tracker, args.repo_target, args.doc,
            args.approval_id, args.approval_status,
            timestamp=sdd_time.ts_now(),
        )
    except ValueError as exc:
        output.error(str(exc), hint="Check repo-target, doc name, and status transition")

    if (
        args.repo_target != "coordination"
        and args.approval_status == "approved"
        and args.doc in workspace.DOC_PHASES
    ):
        try:
            workspace.update_doc_status(
                tracker, args.repo_target, args.doc, "approved",
            )
        except ValueError as exc:
            set_doc_advisories.append({
                "name": "doc-status-update-failed", "level": "warn",
                "message": f"Could not update docStatus: {exc}",
            })

    if args.dry_run:
        dry_data: dict = {"dryRun": True, "tracker": tracker}
        if set_doc_advisories:
            dry_data["advisories"] = set_doc_advisories
        output.success(
            dry_data,
            f"[dry-run] Would record: {args.repo_target}/{args.doc} → "
            f"{args.approval_status}",
            ctx=ctx,
            resolved_from=dict(ctx.resolved_from),
        )
        return

    workspace.finalize_and_save(root, args.feature, tracker)
    success_data: dict = {"tracker": tracker}
    if set_doc_advisories:
        success_data["advisories"] = set_doc_advisories
    output.success(
        success_data,
        f"Approval recorded: {args.repo_target}/{args.doc} → {args.approval_status}",
        ctx=ctx,
        resolved_from=dict(ctx.resolved_from),
        handoffs=handoffs.handoffs_for(handoffs.current_script_id(), ctx),
    )


if __name__ == "__main__":
    cli.run_main(main)
