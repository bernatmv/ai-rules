#!/usr/bin/env python3
"""Bootstrap a workspace feature: coordination-manifest + workspace-tracker.

Usage:
  .spec-workflow/sdd workspace/init-feature.py --target <feature> \
    --repo coordinator:<path>:<feature> \
    --repo target:<path>:<sub-spec> [--repo ...] \
    [--idempotent | --force] [--workspace PATH]

Modes (mutually exclusive):
  default      — first-run create. Refuses if either file already exists.
  --idempotent — first-run create OR no-op when both files exist with
                 a byte-identical projection of the supplied repos.
                 Diff in repos → preflight_required (gate=feature-drift).
  --force      — H1-gated destructive replace. Refuses without
                 SDD_HUMAN_APPROVAL=1; with the env var set, writes
                 a pre-overwrite snapshot then replaces both files.

Schema knowledge lives in `sdd_core.workspace_manifest` and
`sdd_core.workspace_tracker` factories — this shim is purely the
argparse driver + mode-dispatch glue.
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import argparse
import os
import shutil
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable

from sdd_core import cli, handoffs, output
from sdd_core import time as sdd_time
from sdd_core import workspace_manifest, workspace_tracker
from sdd_core.command_templates import (
    build_workspace_init_feature_command,
    build_workspace_update_manifest_command,
)
from sdd_core.paths import (
    COORDINATION_MANIFEST_FILENAME,
    STATE_DIR_NAME,
    WORKSPACE_TRACKER_FILENAME,
    workspace_dir,
)
from sdd_core.transient_state import cleanup_on_approval
from sdd_core.workspace_artifacts import iter_review_quality_files
from sdd_core.security.actor import ActorKind, default_actor_policy
from sdd_core.security.audit import (
    EVENT_FEATURE_BOOTSTRAPPED,
    EVENT_FEATURE_BOOTSTRAP_REPLACED,
    EVENT_FEATURE_BOOTSTRAP_REPLACED_COMMITTED,
    audit_sink,
    build_audit_entry,
)

# Mirrors workflow-graph.json `sdd-workspace-create-spec.context_needs`.
__sdd_context_needs__ = ("target", "workspace")


# Advisory + subcommand identifiers surfaced when a repo's free-form
# ``role`` field is still empty after bootstrap. Centralised so a
# rename in one place propagates without grep-and-replace.
_ADVISORY_KIND_ROLE_UNSET = "manifest-role-unset"
_ADVISORY_KIND_FORCE_SKIPPED_H1 = "force-skipped-h1-pristine"
# Gate identifiers surfaced via ``output.preflight_required``. Hoisted
# so the gate name has a single owner — adding a new gate is one row.
_GATE_FEATURE_DRIFT = "feature-drift"
_GATE_H1_HUMAN_ACTOR = "h1-human-actor"
_SUBCOMMAND_SET_REPO_ROLE = "set-repo-role"


class BootstrapMode(str, Enum):
    """Mutually-exclusive bootstrap modes; ``.value`` is the wire form."""

    DEFAULT = "default"
    IDEMPOTENT = "idempotent"
    FORCE = "force"


# Placeholder text the operator replaces with a concrete description.
# Lives at module level so the lint that flags inline filename / kind
# literals does not trip on a string repeated across helpers.
_ROLE_PLACEHOLDER = "<short repo-purpose description>"
# Snapshot directory name (workspace-relative) used by ``--force`` to
# preserve pre-overwrite state for audit/restore.
_SNAPSHOT_DIR_NAME = ".snapshots"


class _RepoFlagInvalid(ValueError):
    """``ValueError`` carrying the original repo spec + a suggested correction."""

    def __init__(
        self, message: str, *, original: str, suggested: str,
    ) -> None:
        super().__init__(message)
        self.original = original
        self.suggested = suggested


def _parse_repo_flag(spec: str) -> dict:
    """Parse ``repoType:path:sub-spec[:role]`` into a manifest repo entry.

    The first ``:``-segment is the **repoType discriminator** (one of
    ``coordinator`` / ``target``). The optional fourth segment is the
    free-form ``role`` description. When omitted, ``role`` is left empty
    and surfaces as the ``manifest-role-unset`` advisory. ``id`` defaults
    to the basename of the repo path so the common case stays terse.
    """
    parts = spec.split(":", 3)
    if len(parts) < 3:
        raise ValueError(
            f"--repo expects repoType:path:sub-spec[:role], got {spec!r}"
        )
    repo_type, path, sub_spec = parts[0], parts[1], parts[2]
    role = parts[3] if len(parts) == 4 else ""
    if repo_type not in ("coordinator", "target"):
        raise ValueError(
            f"--repo first segment must be 'coordinator' or 'target', "
            f"got {repo_type!r}"
        )
    repo_id = os.path.basename(path.rstrip("/")) or sub_spec
    try:
        workspace_manifest.validate_repo_id(repo_id)
    except ValueError as exc:
        absolute_path = os.path.abspath(path)
        suggested_parts = [repo_type, absolute_path, sub_spec]
        if role:
            suggested_parts.append(role)
        suggested = ":".join(suggested_parts)
        raise _RepoFlagInvalid(
            f"--repo path {path!r} produces invalid id {repo_id!r}: {exc} "
            f"Use an absolute path (e.g. /abs/path/to/repo) or a path "
            f"whose final segment matches "
            f"{workspace_manifest.REPO_ID_REGEX.pattern}.",
            original=spec,
            suggested=suggested,
        )
    return {
        "id": repo_id,
        "name": repo_id,
        "path": path,
        "role": role,
        "repoType": repo_type,
        "subSpec": sub_spec,
    }


def _existing_files(root: Path, feature: str) -> tuple[Path, Path, bool, bool]:
    wd = workspace_dir(root, feature)
    manifest_path = wd / COORDINATION_MANIFEST_FILENAME
    tracker_path = wd / WORKSPACE_TRACKER_FILENAME
    return (
        manifest_path, tracker_path,
        manifest_path.is_file(), tracker_path.is_file(),
    )


def _emit_audit(event: str, *, feature: str, mode: str) -> None:
    """Best-effort audit row — never fails the bootstrap."""
    try:
        actor_kind = default_actor_policy().authorise(
            env=os.environ, args=argparse.Namespace(),
        )
        audit_sink().emit(channel="workspace", entry=build_audit_entry(
            type=event,
            actor="ai-agent",
            actor_kind=actor_kind,
            timestamp=sdd_time.ts_now(),
            target_name=feature,
            category="workspace",
            metadata={"mode": mode},
        ))
    except (OSError, ValueError, KeyError):
        pass


def _snapshot_state(
    root: Path, feature: str, repos: list[dict],
) -> tuple[Path, list[Path]]:
    """Copy manifest, tracker, and per-repo review-quality / sdd-state into the snapshot dir.
    Returns (snapshot_dir, originals) so the caller can unlink originals after copy."""
    wd = workspace_dir(root, feature)
    snap_root = wd / _SNAPSHOT_DIR_NAME / sdd_time.ts_now().replace(":", "-")
    snap_root.mkdir(parents=True, exist_ok=True)
    for fn in (COORDINATION_MANIFEST_FILENAME, WORKSPACE_TRACKER_FILENAME):
        src = wd / fn
        if src.is_file():
            shutil.copy2(src, snap_root / fn)

    review_quality_originals: list[Path] = []
    for repo in repos:
        repo_id = repo.get("id") or ""
        repo_path = repo.get("path") or ""
        sub_spec = repo.get("subSpec") or ""
        if not (repo_id and repo_path and sub_spec):
            continue
        repo_root = (root / repo_path).resolve()
        repo_snap_dir = snap_root / "repos" / repo_id
        for src in iter_review_quality_files(repo_root, sub_spec):
            repo_snap_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, repo_snap_dir / src.name)
            review_quality_originals.append(src)
        # Snapshot per-sub-spec transient state (gate-session.json,
        # staging.json) before --force purges them via
        # cleanup_on_approval. Stale gate sessions would otherwise
        # survive the rerun and pin the new bootstrap to the previous
        # gate's pending tool calls.
        sub_spec_state = (
            repo_root / ".spec-workflow" / "specs" / sub_spec / STATE_DIR_NAME
        )
        if sub_spec_state.is_dir():
            target = repo_snap_dir / "sdd-state"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(sub_spec_state, target, dirs_exist_ok=True)

    return snap_root, review_quality_originals


def _create(
    root: Path, feature: str, repos: list[dict],
) -> tuple[Path, Path]:
    manifest_path = workspace_manifest.write_initial_manifest(
        root, feature, repos,
    )
    tracker_path = workspace_tracker.write_initial_tracker(
        root, feature, repos,
    )
    return manifest_path, tracker_path


def _retry_command(feature: str, repos: list[str], *, mode: str) -> str:
    return build_workspace_init_feature_command(
        feature=feature, repos=repos, mode=mode,
    )


def _build_success_payload(
    feature: str,
    manifest_path: Path,
    tracker_path: Path,
    mode: str,
    *,
    snapshot: "Path | None" = None,
    advisories: "list[dict] | None" = None,
    review_quality_reset: "list[str] | None" = None,
    transient_state_reset: "list[str] | None" = None,
) -> dict:
    """Compose the canonical success payload shape.

    Single emitter for the three branches' success payloads — adds /
    renames a key in one place. Empty extras are dropped so envelope
    diffs against the prior shape stay clean.
    """
    payload: dict = {
        "feature": feature,
        "manifest": str(manifest_path),
        "tracker": str(tracker_path),
        "mode": mode,
    }
    if snapshot is not None:
        payload["snapshot"] = str(snapshot)
    if review_quality_reset:
        payload["review_quality_reset"] = review_quality_reset
    if transient_state_reset:
        payload["transient_state_reset"] = transient_state_reset
    if advisories:
        payload["advisories"] = advisories
    return payload


def _emit_success(ctx, payload: dict, message: str) -> None:
    """Forward to ``output.success`` with the standard handoff envelope."""
    output.success(
        payload,
        message,
        ctx=ctx,
        resolved_from=dict(ctx.resolved_from),
        handoffs=handoffs.handoffs_for(handoffs.current_script_id(), ctx),
    )


@dataclass(frozen=True)
class RunOutcome:
    """Success-branch return shape for every bootstrap mode handler.

    ``payload`` feeds :func:`_emit_success`; ``message`` is the
    human-readable summary. Non-success branches (error / miss /
    preflight_required) are emitted by the handler directly via
    ``output.*`` which exits the process — handlers only return when
    the run resolved into the canonical success envelope.
    """

    payload: dict
    message: str


def _select_mode(args: argparse.Namespace) -> BootstrapMode:
    """Map mutually-exclusive CLI flags onto a :class:`BootstrapMode`."""
    if args.idempotent:
        return BootstrapMode.IDEMPOTENT
    if args.force:
        return BootstrapMode.FORCE
    return BootstrapMode.DEFAULT


def _parse_repos_or_error(raw_specs: list[str]) -> list[dict]:
    """Parse ``--repo`` flags or surface a structured error envelope."""
    try:
        return [_parse_repo_flag(s) for s in raw_specs]
    except _RepoFlagInvalid as exc:
        output.error(
            str(exc),
            hint="--repo value must be repoType:path:sub-spec.",
            kind="invalid_value",
            did_you_mean=[exc.suggested],
        )
    except ValueError as exc:
        output.error(
            str(exc),
            hint="--repo value must be repoType:path:sub-spec.",
        )
    return []  # unreachable — output.error exits


def _missing_role_advisories(feature: str, repos: list[dict]) -> list[dict]:
    """One ``manifest-role-unset`` advisory per repo with empty role.

    The post-bootstrap remediation is the canonical
    ``workspace/update-manifest.py set-repo-role`` shim — emitted via
    :func:`sdd_core.command_templates.build_workspace_update_manifest_command`
    so the literal stays in one place.
    """
    advisories: list[dict] = []
    for repo in repos:
        if repo.get("role"):
            continue
        repo_id = repo.get("id", "")
        if not repo_id:
            continue
        advisories.append({
            "kind": _ADVISORY_KIND_ROLE_UNSET,
            "repoId": repo_id,
            "next_action_command": build_workspace_update_manifest_command(
                feature=feature,
                subcommand=_SUBCOMMAND_SET_REPO_ROLE,
                repo_id=repo_id,
                role=_ROLE_PLACEHOLDER,
            ),
        })
    return advisories


def _run_default(
    ctx, root: Path, feature: str, repos: list[dict],
    raw_repo_specs: list[str], advisories: list[dict],
) -> RunOutcome:
    """Default mode: refuse when manifest or tracker already exist."""
    _, _, m_exists, t_exists = _existing_files(root, feature)
    mode = BootstrapMode.DEFAULT.value
    if m_exists or t_exists:
        output.error(
            f"Feature {feature!r} already bootstrapped at {workspace_dir(root, feature)}; "
            "rerun with --idempotent (no-op when matching) or --force "
            "(H1-gated destructive replace).",
            hint="--idempotent is the safe default for re-runs.",
            next_action_command=_retry_command(
                feature, raw_repo_specs, mode=BootstrapMode.IDEMPOTENT.value,
            ),
        )
    manifest_path, tracker_path = _create(root, feature, repos)
    _emit_audit(EVENT_FEATURE_BOOTSTRAPPED, feature=feature, mode=mode)
    payload = _build_success_payload(
        feature, manifest_path, tracker_path, mode,
        advisories=advisories,
    )
    return RunOutcome(payload=payload, message=f"Bootstrapped feature {feature!r}")


def _run_idempotent(
    ctx, root: Path, feature: str, repos: list[dict],
    raw_repo_specs: list[str], advisories: list[dict],
) -> RunOutcome:
    """Idempotent mode: first-run create OR no-op when repos match."""
    manifest_path, tracker_path, m_exists, t_exists = _existing_files(root, feature)
    mode = BootstrapMode.IDEMPOTENT.value
    if not (m_exists and t_exists):
        manifest_path, tracker_path = _create(root, feature, repos)
        _emit_audit(EVENT_FEATURE_BOOTSTRAPPED, feature=feature, mode=mode)
        payload = _build_success_payload(
            feature, manifest_path, tracker_path, mode,
            advisories=advisories,
        )
        return RunOutcome(
            payload=payload,
            message=f"Bootstrapped feature {feature!r} (idempotent first-run)",
        )
    existing_manifest = workspace_manifest.read_manifest(root, feature)
    existing_tracker = workspace_tracker.read_tracker(root, feature)
    m_match = workspace_manifest.manifest_repos_match(existing_manifest, repos)
    t_match = workspace_tracker.tracker_repos_match(existing_tracker, repos)
    if m_match and t_match:
        output.miss(
            {
                "feature": feature,
                "manifest": str(manifest_path),
                "tracker": str(tracker_path),
                "mode": mode,
            },
            f"Feature {feature!r} already bootstrapped — no-op.",
        )
    output.preflight_required(
        {
            "feature": feature,
            "gate": _GATE_FEATURE_DRIFT,
            "manifestMatched": m_match,
            "trackerMatched": t_match,
        },
        f"Feature {feature!r} repo set drifted from supplied --repo flags.",
        next_action_command=_retry_command(
            feature, raw_repo_specs, mode=BootstrapMode.FORCE.value,
        ),
        hint=(
            "Re-run with --force (H1-gated) to replace, or update the "
            "--repo flags to match the existing manifest."
        ),
        ctx=ctx,
        resolved_from=dict(ctx.resolved_from),
    )
    return RunOutcome(payload={}, message="")  # unreachable — output.* exits


def _run_force(
    ctx, root: Path, feature: str, repos: list[dict],
    raw_repo_specs: list[str], advisories: list[dict],
) -> RunOutcome:
    """Force mode: H1-gated destructive replace with snapshot."""
    _, _, m_exists, t_exists = _existing_files(root, feature)
    mode = BootstrapMode.FORCE.value
    actor_kind = default_actor_policy().authorise(
        env=os.environ, args=argparse.Namespace(),
    )
    freshness = workspace_manifest.bootstrap_freshness(root, feature)
    force_skipped_h1_pristine = False
    if actor_kind is not ActorKind.HUMAN and freshness.is_pristine:
        actor_kind = ActorKind.HUMAN
        force_skipped_h1_pristine = True
    if actor_kind is not ActorKind.HUMAN:
        retry = _retry_command(feature, raw_repo_specs, mode=mode)
        output.preflight_required(
            {
                "feature": feature,
                "gate": _GATE_H1_HUMAN_ACTOR,
            },
            f"--force replace of feature {feature!r} requires SDD_HUMAN_APPROVAL=1.",
            next_action_command=f"SDD_HUMAN_APPROVAL=1 {retry}",
            hint=(
                "Confirm the destructive replace with the human-approval "
                "ceremony, then re-run with the env var set."
            ),
            ctx=ctx,
            resolved_from=dict(ctx.resolved_from),
        )

    snap_dir: "Path | None" = None
    review_quality_reset: list[str] = []
    transient_state_reset: list[str] = []
    if m_exists or t_exists:
        snap_dir, originals = _snapshot_state(root, feature, repos)
        # Drop stale review-quality*.json so the post-bootstrap review
        # pipeline starts from a clean slate. Originals were snapshotted
        # first so deletion is recoverable.
        for src in originals:
            try:
                src.unlink()
                review_quality_reset.append(str(src))
            except OSError:
                pass
        # Purge per-sub-spec transient state (gate-session.json,
        # staging.json) so the new bootstrap is not haunted by a
        # leftover gate session.
        for repo in repos:
            sub_spec = repo.get("subSpec") or ""
            repo_path = repo.get("path") or ""
            if not (sub_spec and repo_path):
                continue
            repo_root = (root / repo_path).resolve()
            try:
                report = cleanup_on_approval(
                    category="spec",
                    target_name=sub_spec,
                    outcome="rejected",
                    project_path=str(repo_root),
                )
            except (OSError, ValueError, KeyError):
                continue
            transient_state_reset.extend(str(p) for p in report.deleted)
    _emit_audit(EVENT_FEATURE_BOOTSTRAP_REPLACED, feature=feature, mode=mode)
    manifest_path, tracker_path = _create(root, feature, repos)
    _emit_audit(EVENT_FEATURE_BOOTSTRAP_REPLACED_COMMITTED, feature=feature, mode=mode)
    if force_skipped_h1_pristine:
        advisories = list(advisories) + [{
            "kind": _ADVISORY_KIND_FORCE_SKIPPED_H1,
            "level": "info",
            "message": (
                f"--force skipped the H1 ceremony because the workspace was "
                f"pristine (younger than "
                f"{workspace_manifest.BOOTSTRAP_PRISTINE_TTL_SECONDS}s, no "
                f"requirements/design/tasks docs present)."
            ),
        }]
    payload = _build_success_payload(
        feature, manifest_path, tracker_path, mode,
        snapshot=snap_dir,
        advisories=advisories,
        review_quality_reset=review_quality_reset,
        transient_state_reset=transient_state_reset,
    )
    return RunOutcome(payload=payload, message=f"Force-replaced feature {feature!r}")


_MODE_HANDLERS: "dict[BootstrapMode, Callable[..., RunOutcome]]" = {
    BootstrapMode.DEFAULT: _run_default,
    BootstrapMode.IDEMPOTENT: _run_idempotent,
    BootstrapMode.FORCE: _run_force,
}


def main() -> None:
    parser = cli.strict_parser(__doc__)
    cli.target_argument(parser, family="workspace")
    parser.add_argument(
        "--repo", action="append", required=True,
        help=(
            "Repeatable repoType:path:sub-spec triple "
            "(e.g. target:./repo:auth-api). "
            "repoType is one of 'coordinator' or 'target'."
        ),
    )
    mx = parser.add_mutually_exclusive_group()
    mx.add_argument(
        "--idempotent", action="store_true",
        help="No-op when manifest+tracker exist and match supplied repos.",
    )
    mx.add_argument(
        "--force", action="store_true",
        help="H1-gated destructive replace (writes pre-overwrite snapshot).",
    )
    args = parser.parse_args()
    ctx = cli.resolve_context(args, needs=("target", "workspace"))

    feature = args.feature
    raw_repo_specs: list[str] = list(args.repo or [])
    repos = _parse_repos_or_error(raw_repo_specs)
    # init-feature bootstraps a fresh workspace; `.spec-workflow/` may
    # not exist yet, so we cannot route through ``cli.resolve_workspace_root``
    # (which requires an existing root). Use the raw flag value.
    root = Path(args.project_path or ".").resolve()
    mode = _select_mode(args)
    advisories = _missing_role_advisories(feature, repos)
    outcome = _MODE_HANDLERS[mode](
        ctx, root, feature, repos, raw_repo_specs, advisories,
    )
    _emit_success(ctx, outcome.payload, outcome.message)


if __name__ == "__main__":
    cli.run_main(main)
