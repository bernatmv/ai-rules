#!/usr/bin/env python3
"""Snapshot review-quality.json and mark the doc reviewed in one shim.

Usage:
  snapshot-and-mark-reviewed.py
    --target <feature>/<repo-id>
    --phase {requirements|design|tasks}
    [--workspace PATH]

Fuses two operations the agent had to remember to do in sequence:

  1. ``cp <repo>/.spec-workflow/specs/<sub-spec>/review-quality.json
        <repo>/.../review-quality-{phase}.json``
  2. ``workspace/update-tracker.py --target <feature> --repo-id <id>
        --phase <phase> --doc-status reviewed``

These two are repeatedly skipped under the agent-memory-only path.
The shim makes them atomic at the operation level: the snapshot is
written via :func:`output.atomic_write_json` (temp-file + rename +
fsync), then the tracker is updated. If any step after the snapshot
write fails — including non-``OSError`` validation failures inside
the tracker update — the destination snapshot is unlinked (or the
prior snapshot restored) so the ``review-artifact-required`` gate
stays consistent with the tracker's docStatus.
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import argparse
import shutil
from pathlib import Path

from sdd_core import cli, output, workspace
from sdd_core.command_templates import (
    build_review_snapshot_command,
    build_workspace_phase_approve_command,
)
from sdd_core.workspace_artifacts import review_artifact_path
from sdd_core.workspace_phase import DOC_PHASES


def _rollback_snapshot(dst: Path, snapshot_backup: "Path | None") -> None:
    """Best-effort rollback: drop the new snapshot and restore the prior one.

    Why: the snapshot file and the tracker docStatus must move
    together — the gate observes both. A half-applied state would
    surface as a missing artifact while the tracker still reports
    'reviewed', defeating the point of the fused shim.
    """
    try:
        if dst.is_file():
            dst.unlink()
    except OSError:
        pass
    if snapshot_backup is not None and snapshot_backup.is_file():
        try:
            shutil.move(str(snapshot_backup), str(dst))
        except OSError:
            pass


def _resolve_repo_path(tracker: dict, repo_id: str) -> "tuple[str, str] | None":
    """Return ``(repo_path, sub_spec_name)`` for *repo_id* in *tracker*.

    Tracker is the authoritative source for sub-spec ↔ repo mapping —
    bouncing through it (rather than the manifest) means the shim
    works whether or not the manifest's role field is populated.
    """
    for sub in tracker.get("subSpecs", []) or []:
        if sub.get("repoId") == repo_id:
            return sub.get("repoPath", ""), sub.get("subSpecName", "")
    return None


def main() -> None:
    parser = cli.workspace_parser(__doc__)
    parser.add_argument(
        "--phase", required=True, choices=DOC_PHASES,
        help=(
            "Document phase whose review-quality.json should be "
            "snapshotted and marked reviewed."
        ),
    )
    args = parser.parse_args()

    ctx = cli.resolve_context(args, needs=("target", "workspace", "repo_id"))
    feature = ctx.feature
    repo_id = ctx.repo_id
    if not feature:
        output.error(
            "--target <feature>/<repo-id> is required",
            hint="e.g. --target auth-feature/api-svc",
        )
    if not repo_id:
        output.error(
            "--target must be `<feature>/<repo-id>`",
            hint="e.g. --target auth-feature/api-svc",
        )
    phase = args.phase
    root = cli.resolve_workspace_root(args)

    tracker = workspace.require_tracker(
        root, feature, hint="Run workspace/init-feature.py first.",
    )
    resolved = _resolve_repo_path(tracker, repo_id)
    if resolved is None:
        known = sorted(
            s.get("repoId", "") for s in tracker.get("subSpecs", []) or []
        )
        output.error(
            f"Unknown repo-id {repo_id!r} in tracker for feature {feature!r}",
            hint=f"Known repo ids: {known}",
        )
    repo_path_raw, sub_spec = resolved
    repo_root = (root / repo_path_raw).resolve()
    spec_dir = repo_root / ".spec-workflow" / "specs" / sub_spec

    src = spec_dir / "review-quality.json"
    if not src.is_file():
        output.error(
            f"Source review-quality.json not found at {src}",
            hint=(
                "Run the sub-agent review (sdd-review-spec-docs) for this "
                "doc before snapshotting."
            ),
        )

    dst = review_artifact_path(repo_root, sub_spec, phase)
    pre_existing_snapshot = dst.is_file()
    snapshot_backup: "Path | None" = None
    next_cmd_retry = build_review_snapshot_command(
        feature=feature, repo_id=repo_id, phase=phase,
        workspace_path=str(root) if str(root) != "." else ".",
    )
    try:
        payload = output.safe_read_json(src)
        if payload is None:
            output.error(
                f"Source review-quality.json could not be read at {src}",
                hint="The file may have been removed concurrently.",
            )
        if pre_existing_snapshot:
            snapshot_backup = dst.with_suffix(".json.bak")
            shutil.move(str(dst), str(snapshot_backup))
        dst.parent.mkdir(parents=True, exist_ok=True)
        # Durable write: temp-file + rename + fsync via the canonical
        # primitive, so a crash mid-write cannot leave a partial file.
        output.atomic_write_json(str(dst), payload)
    except OSError as exc:
        if snapshot_backup is not None and snapshot_backup.is_file():
            try:
                if dst.is_file():
                    dst.unlink()
                shutil.move(str(snapshot_backup), str(dst))
            except OSError:
                pass
        output.error(
            f"Snapshot write failed: {exc}",
            hint="Check filesystem permissions and disk space.",
            next_action_command=next_cmd_retry,
        )

    # Tracker update is the second side-effect; any failure (including
    # non-OSError validation errors) rolls the snapshot back so the
    # gate keeps observing a consistent docStatus / artifact pair.
    try:
        try:
            workspace.update_doc_status(tracker, repo_id, phase, "reviewed")
        except ValueError as exc:
            _rollback_snapshot(dst, snapshot_backup)
            output.error(
                f"Could not set docStatus.{phase} to 'reviewed': {exc}",
                hint=(
                    "Check DOC_STATUS_TRANSITIONS in workspace_phase.py "
                    "for valid transitions."
                ),
                next_action_command=next_cmd_retry,
            )
        workspace.finalize_and_save(root, feature, tracker)
    except Exception as exc:  # noqa: BLE001 — preserve atomic contract
        _rollback_snapshot(dst, snapshot_backup)
        output.error(
            f"Tracker update failed after snapshot write: {exc}",
            hint=(
                "Snapshot was rolled back; the gate state is consistent. "
                "Re-run the same shim once the underlying issue is resolved."
            ),
            next_action_command=next_cmd_retry,
        )
    if snapshot_backup is not None and snapshot_backup.is_file():
        try:
            snapshot_backup.unlink()
        except OSError:
            pass

    next_cmd = build_workspace_phase_approve_command(
        feature=feature, doc=phase,
        workspace_path=str(root) if str(root) != "." else ".",
    )
    output.success(
        {
            "feature": feature,
            "repoId": repo_id,
            "phase": phase,
            "snapshot": str(dst),
            "trackerDocStatus": "reviewed",
            "next_action_command": next_cmd,
        },
        f"Snapshot + tracker updated: {repo_id}/{phase} → reviewed.",
    )


if __name__ == "__main__":
    cli.run_main(main)
