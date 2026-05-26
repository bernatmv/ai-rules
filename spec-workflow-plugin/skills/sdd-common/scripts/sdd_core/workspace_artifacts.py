"""Workspace approval artifact creation (approval JSON, snapshots, audit entries).

Extracted from workspace_approval.py to isolate per-repo I/O concerns
from the batch/phase approval orchestration logic.
"""
from __future__ import annotations

__all__ = [
    "EVENT_APPROVAL_ATTEMPT_REJECTED",
    "EVENT_APPROVAL_STATUS_CHANGE",
    "RepoApprovalResult",
    "build_audit_entry",
    "create_repo_approval_artifacts",
    "iter_review_quality_files",
    "review_artifact_path",
    "REVIEW_QUALITY_GLOB",
    "REVIEW_QUALITY_PHASE_TEMPLATE",
]

import argparse
import os
from pathlib import Path
from typing import Iterator, Literal, TypedDict


# Match ``review-quality.json`` plus per-phase snapshots like
# ``review-quality-requirements.json``. Single source of truth for
# the ``--force`` reset and any future audit walker.
REVIEW_QUALITY_GLOB = "review-quality*.json"

# Format string for the per-phase snapshot filename. Used by the
# canonical path helper and by every consumer that names the file
# directly (the snapshot shim and the workspace gate). Single source
# of truth for the snapshot naming convention.
REVIEW_QUALITY_PHASE_TEMPLATE = "review-quality-{phase}.json"

from . import output as _output
from .security.actor import ActorKind, default_actor_policy
from .security.audit import (
    EVENT_APPROVAL_ATTEMPT_REJECTED,
    EVENT_APPROVAL_STATUS_CHANGE,
    audit_sink,
    build_audit_entry,
)
from .workspace_tracker import TrackerSubSpec


RepoApprovalOutcome = Literal["approved", "preflight_required", "failed"]


class RepoApprovalResult(TypedDict, total=False):
    """Structured outcome of one repo's per-doc approval attempt."""

    repoId: str
    outcome: RepoApprovalOutcome
    gate: str
    reason: str
    approvalId: str


def review_artifact_path(repo_path: "Path | str", sub_spec: str, phase: str) -> Path:
    """Canonical location of ``review-quality-{phase}.json`` for a repo × phase."""
    return (
        Path(repo_path) / ".spec-workflow" / "specs" / sub_spec
        / REVIEW_QUALITY_PHASE_TEMPLATE.format(phase=phase)
    )


def iter_review_quality_files(
    repo_root: "Path | str", sub_spec: str,
) -> Iterator[Path]:
    """Yield every ``review-quality*.json`` file for ``sub_spec`` in a repo.

    Single source of truth for "which review-quality files belong to this
    sub-spec" — both ``init-feature.py --force`` (reset) and any audit
    walker depend on this projection so the layout is owned in one place
    instead of being re-walked from the filesystem at every call site.
    """
    spec_dir = Path(repo_root) / ".spec-workflow" / "specs" / sub_spec
    if not spec_dir.is_dir():
        return
    for path in sorted(spec_dir.glob(REVIEW_QUALITY_GLOB)):
        if path.is_file():
            yield path


def create_repo_approval_artifacts(
    sub: TrackerSubSpec, doc: str, approval_id: str, timestamp: str,
) -> RepoApprovalResult:
    """Best-effort: create approval JSON, snapshot, and audit entry in a repo.

    Failures are logged as warnings — the tracker update is the primary
    record.  Approval artifacts provide supplementary auditability.

    Routes every audit-log write through :func:`audit_sink` so the
    seam owns the durability contract (R1). The H1 actor-kind gate
    refuses to commit an ``approved`` row when the calling environment
    is not human-attested; the rejected attempt is still recorded as
    an immutable ``approval-attempt-rejected`` entry for forensics.
    """
    from . import approvals, snapshots, paths

    repo_id = sub.get("repoId", "")
    repo_path_str = sub.get("repoPath", "")
    sub_spec_name = sub.get("subSpecName", "")
    if not repo_path_str or not sub_spec_name:
        return RepoApprovalResult(
            repoId=repo_id, outcome="failed",
            gate="missing-repo-fields",
            reason="repoPath / subSpecName missing on tracker entry",
        )

    repo_path = Path(repo_path_str)
    doc_rel_path = f".spec-workflow/specs/{sub_spec_name}/{doc}.md"
    title = f"Workspace {doc}: {sub_spec_name}"

    actor_kind = default_actor_policy().authorise(
        env=os.environ, args=argparse.Namespace(),
    )
    if actor_kind is not ActorKind.HUMAN:
        try:
            audit_sink().emit(channel="approval", entry=build_audit_entry(
                type=EVENT_APPROVAL_ATTEMPT_REJECTED,
                actor="ai-agent",
                actor_kind=actor_kind,
                timestamp=timestamp,
                approval_id=approval_id,
                title=title,
                filePath=doc_rel_path,
                category="spec",
                categoryName=sub_spec_name,
                document=f"{doc}.md",
                gate="h1-human-actor",
                metadata={"triggerContext": "batch-approval"},
                target_name=sub_spec_name,
                project_path=str(repo_path),
            ))
        except Exception as exc:  # noqa: BLE001 — never block batch approval flow
            _output.warn(
                f"Audit emit (h1-attempt-rejected) skipped: {exc}."
            )
        return RepoApprovalResult(
            repoId=repo_id, outcome="preflight_required",
            gate="h1-human-actor",
            reason=(
                "Workspace batch approval requires SDD_HUMAN_APPROVAL=1 "
                "to commit the per-repo approval artifact."
            ),
        )

    try:
        appr_dir = paths.approvals_dir(repo_path, sub_spec_name)
        appr_dir.mkdir(parents=True, exist_ok=True)
        approvals.write_approval(appr_dir / f"{approval_id}.json", {
            "id": approval_id,
            "title": title,
            "filePath": doc_rel_path,
            "type": "document",
            "status": "approved",
            "category": "spec",
            "categoryName": sub_spec_name,
            "createdAt": timestamp,
        })

        snap_dir = paths.snapshots_dir(repo_path, sub_spec_name, f"{doc}.md")
        snapshots.create_snapshot(
            repo_path / doc_rel_path, approval_id,
            f"Workspace batch approval: {doc}",
            "approved", "approved", snap_dir,
            canonical_path=doc_rel_path,
        )

        audit_sink().emit(channel="approval", entry=build_audit_entry(
            type=EVENT_APPROVAL_STATUS_CHANGE,
            actor="ai-agent",
            actor_kind=actor_kind,
            timestamp=timestamp,
            approval_id=approval_id,
            title=title,
            filePath=doc_rel_path,
            category="spec",
            categoryName=sub_spec_name,
            document=f"{doc}.md",
            previousStatus="reviewed",
            newStatus="approved",
            response=f"Workspace batch approval for {doc}",
            metadata={"triggerContext": "batch-approval"},
            project_path=str(repo_path),
            target_name=sub_spec_name,
        ))
        return RepoApprovalResult(
            repoId=repo_id, outcome="approved",
            approvalId=approval_id,
        )
    except OSError as exc:
        return RepoApprovalResult(
            repoId=repo_id, outcome="failed",
            gate="repo-io",
            reason=f"Approval artifact creation failed: {exc}",
        )
