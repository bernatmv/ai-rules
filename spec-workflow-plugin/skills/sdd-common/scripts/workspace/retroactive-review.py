#!/usr/bin/env python3
"""Retroactive workspace-review tool.

Walks a workspace tracker and surfaces every (sub-spec, phase) pair
whose ``docStatus.{phase} = reviewed`` (or beyond) but is missing the
``review-quality.json`` artifact. Emits an action plan the operator
can drive forward; on subsequent invocations stamps
``reviewMeta.{phase}.retroactive=true`` for repos whose artifact is
now present.

Usage:
  .spec-workflow/sdd workspace/retroactive-review.py --target <feature> \
    [--phase requirements|design|tasks] [--phase-repo-id ID] [--dry-run]
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import argparse
import os
from pathlib import Path

from sdd_core import cli, handoffs, output
from sdd_core import time as sdd_time
from sdd_core import workspace
from sdd_core.command_templates import build_retroactive_review_command
from sdd_core.security.actor import ActorKind, default_actor_policy
from sdd_core.security.audit import (
    EVENT_REVIEW_RETROACTIVE_COMPLETED,
    audit_sink,
    build_audit_entry,
)
from sdd_core.workspace_artifacts import review_artifact_path as _review_artifact_path
from sdd_core.workspace_phase import DOC_PHASES as _PHASES


# Mirrors workflow-graph.json `sdd-workspace-create-spec.context_needs`.
__sdd_context_needs__ = ("target", "workspace", "repo_id")
_REVIEWED_OR_BEYOND: frozenset[str] = frozenset({"reviewed", "approved"})


def _scan_missing(
    tracker: dict, *, phase_filter: "str | None", repo_id_filter: "str | None",
) -> list[dict]:
    missing: list[dict] = []
    sub_specs = tracker.get("subSpecs", []) or []
    for sub in sub_specs:
        repo_id = sub.get("repoId", "")
        if repo_id_filter and repo_id != repo_id_filter:
            continue
        repo_path = sub.get("repoPath", "")
        sub_spec = sub.get("subSpecName", "")
        doc_status = sub.get("docStatus", {}) or {}
        review_meta = sub.get("reviewMeta", {}) or {}
        for phase in _PHASES:
            if phase_filter and phase != phase_filter:
                continue
            status = doc_status.get(phase, "")
            if status not in _REVIEWED_OR_BEYOND:
                continue
            if review_meta.get(phase, {}).get("reviewSkipped"):
                continue
            artifact = _review_artifact_path(repo_path, sub_spec, phase)
            if artifact.is_file():
                continue
            missing.append({
                "repoId": repo_id,
                "subSpecName": sub_spec,
                "phase": phase,
                "expectedArtifact": str(artifact),
            })
    return missing


def _scan_now_present(
    tracker: dict, *, phase_filter: "str | None", repo_id_filter: "str | None",
) -> list[dict]:
    """Detect (repo, phase) pairs that have an artifact but no retro stamp."""
    found: list[dict] = []
    sub_specs = tracker.get("subSpecs", []) or []
    for sub in sub_specs:
        repo_id = sub.get("repoId", "")
        if repo_id_filter and repo_id != repo_id_filter:
            continue
        repo_path = sub.get("repoPath", "")
        sub_spec = sub.get("subSpecName", "")
        doc_status = sub.get("docStatus", {}) or {}
        review_meta = sub.get("reviewMeta", {}) or {}
        for phase in _PHASES:
            if phase_filter and phase != phase_filter:
                continue
            status = doc_status.get(phase, "")
            if status not in _REVIEWED_OR_BEYOND:
                continue
            artifact = _review_artifact_path(repo_path, sub_spec, phase)
            if not artifact.is_file():
                continue
            phase_meta = review_meta.get(phase, {}) or {}
            if phase_meta.get("retroactive"):
                continue
            found.append({
                "repoId": repo_id,
                "subSpecName": sub_spec,
                "phase": phase,
                "artifact": str(artifact),
            })
    return found


def _emit_audit(*, feature: str, repo_id: str, phase: str) -> None:
    try:
        actor_kind = default_actor_policy().authorise(
            env=os.environ, args=argparse.Namespace(),
        )
        audit_sink().emit(channel="workspace", entry=build_audit_entry(
            type=EVENT_REVIEW_RETROACTIVE_COMPLETED,
            actor="ai-agent",
            actor_kind=actor_kind,
            timestamp=sdd_time.ts_now(),
            target_name=feature,
            category="workspace",
            metadata={"repoId": repo_id, "phase": phase},
        ))
    except Exception:  # noqa: BLE001
        pass


def main() -> None:
    parser = cli.strict_parser(__doc__)
    cli.target_argument(parser, family="workspace")
    parser.add_argument(
        "--phase", choices=list(_PHASES), default=None,
        help="Narrow scope to one phase (default: all phases).",
    )
    parser.add_argument(
        "--phase-repo-id", dest="phase_repo_id", default=None,
        help="Narrow scope to one repo (matches subSpecs[].repoId).",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print the action plan without mutating the tracker.",
    )
    args = parser.parse_args()
    ctx = cli.resolve_context(args, needs=("target", "workspace", "repo_id"))

    feature = args.feature
    # ``--target {feature}/{repo-id}`` populates args.repo_id; keep
    # --phase-repo-id as the explicit override.
    repo_id_filter = args.phase_repo_id or getattr(args, "repo_id", None)
    root = Path(args.project_path or ".").resolve()

    tracker = workspace.require_tracker(root, feature)

    missing = _scan_missing(
        tracker, phase_filter=args.phase, repo_id_filter=repo_id_filter,
    )
    now_present = _scan_now_present(
        tracker, phase_filter=args.phase, repo_id_filter=repo_id_filter,
    )

    if args.dry_run:
        output.success(
            {
                "feature": feature,
                "missingArtifacts": missing,
                "artifactsAwaitingStamp": now_present,
                "dryRun": True,
            },
            f"[dry-run] {len(missing)} missing, {len(now_present)} present-but-unstamped",
            ctx=ctx,
            resolved_from=dict(ctx.resolved_from),
        )
        return

    stamped: list[dict] = []
    retro_advisories: list[dict] = []
    for entry in now_present:
        try:
            workspace.mark_review_retroactive(
                tracker, entry["repoId"], entry["phase"],
                timestamp=sdd_time.ts_now(),
            )
            _emit_audit(feature=feature, repo_id=entry["repoId"], phase=entry["phase"])
            stamped.append(entry)
        except ValueError as exc:
            retro_advisories.append(
                {"name": "stamp-skipped", "level": "warn",
                 "message": f"Skipped {entry['repoId']}/{entry['phase']}: {exc}"}
            )

    if stamped:
        workspace.finalize_and_save(root, feature, tracker)

    if missing:
        retry = build_retroactive_review_command(
            feature=feature, dry_run=True,
        )
        output.preflight_required(
            {
                "feature": feature,
                "gate": "review-artifact-required",
                "missingArtifacts": missing,
                "stamped": stamped,
            },
            f"{len(missing)} (repo × phase) pair(s) still missing review-quality-{{phase}}.json",
            next_action_command=retry,
            hint=(
                "Re-run sdd-review-spec-docs against each missing repo × "
                "phase pair, then re-invoke retroactive-review.py to stamp."
            ),
            ctx=ctx,
            resolved_from=dict(ctx.resolved_from),
        )
        return

    success_payload: dict = {"feature": feature, "stamped": stamped}
    if retro_advisories:
        success_payload["advisories"] = retro_advisories
    output.success(
        success_payload,
        f"Stamped {len(stamped)} retroactive review row(s).",
        ctx=ctx,
        resolved_from=dict(ctx.resolved_from),
        handoffs=handoffs.handoffs_for(handoffs.current_script_id(), ctx),
    )


if __name__ == "__main__":
    cli.run_main(main)
