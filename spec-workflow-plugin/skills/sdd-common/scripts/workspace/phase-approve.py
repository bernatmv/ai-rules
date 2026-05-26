#!/usr/bin/env python3
"""Atomic phase-approve: advance tracker only when every repo is approved.

Usage:
  .spec-workflow/sdd workspace/phase-approve.py --target <feature> \
    --doc <requirements|design|tasks> [--dry-run] [--workspace PATH]

Per-repo H1 refusals surface as ``output.preflight_required`` with a
retry shim wrapped in ``SDD_HUMAN_APPROVAL=1``; tracker stays at
``reviewed`` (W3 atomicity contract).

A separate gate refuses to advance when any repo's
``review-quality.json`` artifact is missing without
``reviewMeta.{phase}.reviewSkipped=true`` (W4 review-artifact gate).
"""
import _bootstrap  # noqa: F401

from pathlib import Path

from sdd_core import cli, handoffs, output, transient_state, workspace
from sdd_core.command_templates import (
    build_review_snapshot_command,
    build_workspace_phase_approve_command,
)
from sdd_core.workspace_artifacts import review_artifact_path
from sdd_core.workspace_phase import DOC_PHASES as _VALID_DOCS

# Mirror of the workflow graph's ``context_needs`` so the
# ``with_context_coverage`` lint can cross-check the resolver call.
__sdd_context_needs__ = ("target", "workspace", "repo_id", "phase")


def _check_review_artifact_presence(
    tracker: dict, doc: str, pending: list[dict],
) -> list[dict]:
    """Return repos missing ``review-quality-{doc}.json`` artifacts.

    A repo is excluded from the check when
    ``reviewMeta.{doc}.reviewSkipped`` is truthy — the review was
    explicitly skipped and the missing artifact is intentional.
    """
    missing: list[dict] = []
    for sub in pending:
        review_meta = sub.get("reviewMeta", {}) or {}
        if (review_meta.get(doc) or {}).get("reviewSkipped"):
            continue
        repo_path = sub.get("repoPath", "")
        sub_spec = sub.get("subSpecName", "")
        if not repo_path or not sub_spec:
            continue
        artifact = review_artifact_path(repo_path, sub_spec, doc)
        if not artifact.is_file():
            missing.append({
                "repoId": sub.get("repoId", ""),
                "subSpecName": sub_spec,
                "repoPath": repo_path,
                "expectedArtifact": str(artifact),
            })
    return missing


def _resolve_doc_default(tracker: dict) -> "str | None":
    """Return ``tracker.currentPhase`` when it names a valid doc."""
    current = tracker.get("currentPhase")
    if current in _VALID_DOCS:
        return current
    return None


def main() -> None:
    parser = cli.strict_parser("Atomic phase-approve workspace")
    cli.add_workspace_arg(parser)
    cli.target_argument(parser, family="workspace")
    parser.add_argument(
        "--doc", default=None,
        choices=list(_VALID_DOCS),
        help=(
            "Document type to approve. Defaults to tracker.currentPhase "
            "when it names one of requirements / design / tasks."
        ),
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview pending approvals without writing to disk",
    )
    args = parser.parse_args()
    root = cli.resolve_workspace_root(args)
    feature = args.feature

    # Pin current target so downstream shims read it from the session
    # instead of re-typing it.
    ctx = cli.resolve_context(
        args, needs=("target", "workspace", "repo_id", "phase"),
    )

    manifest = workspace.require_manifest(root, feature)
    tracker = workspace.require_tracker(
        root, feature, hint="Run update-tracker.py first",
    )

    if args.doc is None:
        resolved = _resolve_doc_default(tracker)
        if resolved is None:
            output.error(
                "--doc not provided and tracker.currentPhase is missing or "
                "not one of requirements / design / tasks",
                hint=(
                    "Pass --doc explicitly, or run "
                    "workspace/advance-phase.py first to set currentPhase."
                ),
                next_action_command=build_workspace_phase_approve_command(
                    feature=feature, doc="<requirements|design|tasks>",
                ),
            )
        args.doc = resolved

    still_validated = workspace.filter_by_doc_status(tracker, args.doc, "validated")
    active_ids = {s.get("repoId") for s in workspace.active_repos(tracker)}
    unreviewed = [s for s in still_validated if s.get("repoId") in active_ids]
    if unreviewed:
        unreviewed_ids = [s.get("repoId", "?") for s in unreviewed]
        output.error(
            f"Cannot approve {args.doc}: {len(unreviewed)} repo(s) still at "
            f"'validated' (not 'reviewed'): {unreviewed_ids}. "
            f"Run the batch review step first (phase-loop.md § Review Step).",
            hint="Each repo must reach docStatus 'reviewed' before approval. "
                 "Use update-tracker.py --doc-status reviewed after review completes, "
                 "or --doc-status reviewed --review-skipped if user chose to skip.",
        )

    pending = workspace.collect_phase_pending(tracker, args.doc)
    if not pending:
        output.success(
            {"feature": feature, "doc": args.doc, "approved": []},
            f"No repos with {args.doc} at 'reviewed' status",
            ctx=ctx,
            resolved_from=dict(ctx.resolved_from),
        )
        return

    # Review-artifact presence gate before any approval write. Emits the
    # snapshot shim as the recovery literal so the agent runs one
    # command that fuses the snapshot copy and the tracker update —
    # neither step is left to memory.
    missing_artifacts = _check_review_artifact_presence(tracker, args.doc, pending)
    if missing_artifacts:
        first = missing_artifacts[0]
        retry = build_review_snapshot_command(
            feature=feature,
            repo_id=first["repoId"],
            phase=args.doc,
            workspace_path=str(root) if str(root) != "." else ".",
        )
        output.preflight_required(
            {
                "feature": feature,
                "doc": args.doc,
                "gate": "review-artifact-required",
                "missingArtifacts": missing_artifacts,
            },
            (
                f"{len(missing_artifacts)} repo(s) missing review-quality-"
                f"{args.doc}.json artifact — cannot approve without the "
                f"review record."
            ),
            next_action_command=retry,
            next_action_command_note=(
                "The shim performs both the snapshot copy and the tracker "
                "docStatus update atomically; do not run them separately."
            ),
            hint=(
                "Run sdd-review-spec-docs (or set "
                "reviewMeta.{phase}.reviewSkipped=true) before re-running."
            ),
            ctx=ctx,
            resolved_from=dict(ctx.resolved_from),
        )

    summary_text = workspace.generate_phase_approval_summary(
        manifest, tracker, pending, args.doc,
    )
    pending_ids = [s.get("repoId") for s in pending]

    if args.dry_run:
        output.success(
            {
                "dryRun": True,
                "feature": feature,
                "doc": args.doc,
                "summary": summary_text,
                "pendingRepoIds": pending_ids,
            },
            f"[dry-run] Would approve {args.doc} for {len(pending)} repo(s): {pending_ids}",
            ctx=ctx,
            resolved_from=dict(ctx.resolved_from),
        )
        return

    result = workspace.apply_phase_approval(
        root, feature, args.doc, pending, tracker=tracker,
    )

    if result["preflight_required"]:
        retry = build_workspace_phase_approve_command(
            feature=feature, doc=args.doc, human_env=True,
        )
        output.preflight_required(
            {
                "feature": feature,
                "doc": args.doc,
                "gate": "h1-human-actor",
                "result": result,
            },
            (
                f"{len(result['preflight_required'])} repo(s) need H1 "
                f"approval ceremony before {args.doc} can advance."
            ),
            next_action_command=retry,
            hint=(
                "Confirm via the human-approval ceremony then re-run "
                "with SDD_HUMAN_APPROVAL=1."
            ),
            ctx=ctx,
            resolved_from=dict(ctx.resolved_from),
        )

    approved_count = len(result["approved"])
    failed_count = len(result["failed"])

    # Pin current-target so the next shim reads ``feature`` / ``doc``
    # from session instead of re-typing.
    project_path = getattr(args, "project_path", None) or ""
    transient_state.write_current_target(
        feature, phase=args.doc, repo_id=args.repo_id or None,
        project_path=project_path,
    )

    output.success(
        {"feature": feature, "doc": args.doc, "result": result},
        f"Phase approved {args.doc}: {approved_count} approved, {failed_count} failed",
        ctx=ctx,
        resolved_from=dict(ctx.resolved_from),
        handoffs=handoffs.handoffs_for(handoffs.current_script_id(), ctx),
    )


if __name__ == "__main__":
    cli.run_main(main)
