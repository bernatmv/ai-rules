#!/usr/bin/env python3
"""Validate a workspace sub-spec for correct structure and metadata.

Usage:
  .spec-workflow/sdd workspace/check-spec-shape.py --workspace <path> \
    --target <sub-spec> [--doc <doc>]
  .spec-workflow/sdd workspace/check-spec-shape.py --workspace <path> \
    --target <sub-spec> --doc <doc> \
    --tracker-root <coordinator-root> --tracker-target <feature>/<repo-id>

When --tracker-root and --tracker-target are provided alongside --doc,
a successful validation automatically updates docStatus.{doc} to
"validated" in the coordinator's workspace tracker.
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, NamedTuple

from sdd_core import cli, handoffs, output, paths, specs, tasks, workspace_validation
from sdd_core.cli import split_workspace_target
from sdd_core.command_templates import build_check_spec_shape_command
from sdd_core.traceability import (
    analyse_traceability, extract_requirement_ids, is_bug_fix_content,
)
from sdd_core.workspace_phase import DOC_PHASES

# Workspace-target subset of ``sdd-workspace-create-spec.context_needs``.
__sdd_context_needs__ = ("target", "workspace", "repo_id")

# Advisory + status literals surfaced when the auto docStatus update
# cannot land. Module-level so renames stay in one place and both the
# ``--tracker-root``-supplied and not-supplied branches reference the
# same string.
_ADVISORY_KIND_TRACKER_UPDATE_SKIPPED = "tracker-update-skipped"
_DOC_STATUS_VALIDATED = "validated"

# Single writer for the orphan-ref message so a future wording change
# lands in one place. ``{ref}`` is filled at the call site.
_ORPHAN_REF_MESSAGE_TEMPLATE = (
    "Task references {ref} which is not a known requirement id "
    "(see troubleshooting → orphan refs)."
)


class _ValidateResult(NamedTuple):
    """Return shape for :func:`_validate` — named for readability."""

    shape: dict
    traceability: list[dict]


@dataclass(frozen=True)
class _SpecResolution:
    """Resolved sub-spec coordinates returned by :func:`_resolve_spec_dir`."""

    spec_root: Path
    spec_name: str
    feature: "str | None"
    repo_id: "str | None"


@dataclass(frozen=True)
class _TrackerOutcome:
    """Result of a tracker docStatus update attempt."""

    kind: Literal["ok", "skipped"]
    payload: dict


def _resolve_spec_dir(
    root: Path, args, feature: "str | None", repo_id: "str | None",
) -> _SpecResolution:
    """Resolve workspace-target ``<feature>/<repo-id>`` into spec coords.

    When ``args.spec_name`` carries a slash, look up the sub-spec on the
    workspace tracker and rebase ``spec_root`` / ``spec_name`` to the
    target repo. Otherwise return the caller-supplied coordinates as-is.
    """
    spec_name = args.spec_name
    if not (spec_name and "/" in spec_name):
        return _SpecResolution(
            spec_root=root, spec_name=spec_name,
            feature=feature, repo_id=repo_id,
        )
    spec_feature, _, spec_repo_id = spec_name.partition("/")
    if not (spec_feature and spec_repo_id):
        return _SpecResolution(
            spec_root=root, spec_name=spec_name,
            feature=feature, repo_id=repo_id,
        )
    from sdd_core import workspace as _ws

    tracker = _ws.read_tracker(root, spec_feature)
    if tracker is None:
        output.error(
            f"Workspace tracker not found for feature {spec_feature!r}",
            hint="Run `workspace/init-feature.py` for the feature first.",
        )
    for sub in tracker.get("subSpecs") or []:
        if sub.get("repoId") == spec_repo_id:
            return _SpecResolution(
                spec_root=(Path(root) / sub.get("repoPath", "")).resolve(),
                spec_name=sub.get("subSpecName", ""),
                feature=feature or spec_feature,
                repo_id=repo_id or spec_repo_id,
            )
    known = sorted(
        s.get("repoId", "") for s in tracker.get("subSpecs") or []
    )
    did_you_mean: list[str] = []
    hint = f"Known repo ids: {known}"
    if not known:
        search_roots = cli.compose_tracker_search_roots(args)
        coord_root = paths.find_coordinator_root_for_feature(
            spec_feature, search_roots=search_roots,
        )
        if coord_root and Path(coord_root).resolve() != Path(root).resolve():
            suggested = build_check_spec_shape_command(
                workspace_path=coord_root,
                feature=spec_feature,
                repo_id=spec_repo_id,
                doc=args.doc or "requirements",
            )
            did_you_mean.append(suggested)
            hint = (
                f"Known repo ids: {known}. The tracker at "
                f"{root!s} carries no repos for this "
                f"feature; the manifest-declared coordinator "
                f"is at {coord_root}. Re-run from there."
            )
    output.error(
        f"Unknown repo-id {spec_repo_id!r} in feature {spec_feature!r}",
        hint=hint,
        kind="invalid_value" if not did_you_mean else "wrong_workspace",
        did_you_mean=did_you_mean or None,
    )
    return _SpecResolution(  # unreachable — output.error exits
        spec_root=root, spec_name=spec_name,
        feature=feature, repo_id=repo_id,
    )


def _resolve_tracker_root_with_fallback(
    args, feature: "str | None",
) -> "Path | None":
    """Resolve ``--tracker-root`` with coordinator-rooted-``--workspace`` fallback.

    Order:
      1. Explicit ``--tracker-root`` (existing semantics; ``cli.resolve_tracker_root``).
      2. ``--workspace`` resolves to an absolute coordinator path AND
         ``--target`` carries ``<feature>/<repo-id>`` slash form
         → compose via ``paths.find_coordinator_root_for_feature``.
      3. ``None`` — caller surfaces the legacy advisory.
    """
    if args.tracker_root:
        return cli.resolve_tracker_root(args)
    if not feature:
        return None
    search_roots = cli.compose_tracker_search_roots(args)
    coord_root = paths.find_coordinator_root_for_feature(
        feature, search_roots=search_roots,
    )
    if not coord_root:
        return None
    workspace_root = (
        getattr(args, "project_path", None)
        or getattr(args, "workspace", None)
        or os.getcwd()
    )
    try:
        coord_resolved = Path(coord_root).resolve()
        ws_resolved = Path(workspace_root).resolve()
    except OSError:
        return None
    if coord_resolved == ws_resolved:
        return coord_resolved
    return None


def _apply_tracker_update(
    tracker_root: Path, *, feature: str, repo_id: str, doc: str,
) -> _TrackerOutcome:
    """Run the tracker docStatus update against a resolved root."""
    from sdd_core import workspace

    outcome = workspace.update_tracker_or_advisory(
        tracker_root, feature, repo_id,
        doc=doc, status=_DOC_STATUS_VALIDATED,
        workspace_path=str(tracker_root),
    )
    if outcome.updated:
        return _TrackerOutcome(
            kind="ok",
            payload={
                "trackerUpdated": True,
                "docStatusSet": _DOC_STATUS_VALIDATED,
            },
        )
    return _TrackerOutcome(
        kind="skipped",
        payload={
            "kind": _ADVISORY_KIND_TRACKER_UPDATE_SKIPPED,
            "reason": outcome.reason,
            "next_action_command": outcome.recovery_command,
        },
    )


def _tracker_update_outcome(
    *, args, feature: str, repo_id: str, doc: str,
) -> _TrackerOutcome:
    """Apply the tracker docStatus update or surface a structured advisory."""
    resolved_tracker_root = _resolve_tracker_root_with_fallback(args, feature)
    if resolved_tracker_root is not None:
        return _apply_tracker_update(
            resolved_tracker_root,
            feature=feature, repo_id=repo_id, doc=doc,
        )
    if args.tracker_root:
        return _TrackerOutcome(
            kind="skipped",
            payload={
                "kind": _ADVISORY_KIND_TRACKER_UPDATE_SKIPPED,
                "reason": "tracker-root-not-resolvable",
            },
        )
    from sdd_core.command_templates import (
        build_workspace_update_tracker_command,
    )

    return _TrackerOutcome(
        kind="skipped",
        payload={
            "kind": _ADVISORY_KIND_TRACKER_UPDATE_SKIPPED,
            "reason": "tracker-root-not-provided",
            "next_action_command": build_workspace_update_tracker_command(
                feature=feature, repo_id=repo_id,
                doc=doc, status=_DOC_STATUS_VALIDATED,
            ),
        },
    )


def _traceability_errors(
    spec_root: Path, spec_name: str,
) -> list[dict]:
    """Run :func:`analyse_traceability` on the sub-spec's req/tasks pair.

    Returns ``[]`` when traceability is full, when either doc is
    missing (the caller's structural pass already flagged that), or
    when the requirements doc carries a bug-fix template (no numeric
    ids to trace). Otherwise returns one error dict per gap so the
    workspace envelope can merge them into ``traceability_errors``.
    """
    req_content = specs.read_spec_doc(spec_root, spec_name, "requirements")
    tasks_content = specs.read_spec_doc(spec_root, spec_name, "tasks")
    if not req_content or not tasks_content:
        return []
    if not extract_requirement_ids(req_content) and is_bug_fix_content(req_content):
        return []
    result = analyse_traceability(req_content, tasks_content)
    if result["result"] != "gaps_found":
        return []
    errors: list[dict] = []
    for missing in result["missing"]:
        errors.append({
            "kind": "uncovered_requirement",
            "message": f"Requirement {missing} has no covering task",
            "requirement_id": missing,
        })
    for orphan in result["orphanRefs"]:
        errors.append({
            "kind": "orphan_ref",
            "message": _ORPHAN_REF_MESSAGE_TEMPLATE.format(ref=orphan),
            "requirement_ref": orphan,
        })
    return errors


def _validate(spec_root: Path, spec_name: str, args) -> _ValidateResult:
    """Run structural + metadata + antipattern validation; merge results.

    Returns a :class:`_ValidateResult` so callers read the two error
    sources by name. ``shape`` keeps the merged ``errors`` /
    ``warnings`` shape; ``traceability`` is the per-orphan list.
    """
    structural = specs.validate_spec_structure(
        spec_root, spec_name, doc_filter=args.doc,
    )
    metadata_result: specs.ValidationResult = {"errors": [], "warnings": []}
    if args.doc is None or args.doc == "tasks":
        tasks_content = specs.read_spec_doc(spec_root, spec_name, "tasks")
        if tasks_content:
            parsed_tasks = tasks.parse_tasks(tasks_content)
            metadata_result = workspace_validation.validate_workspace_metadata(
                parsed_tasks,
            )
    combined = specs.merge_validation_results(structural, metadata_result)
    if args.doc in workspace_validation.ANTIPATTERN_DISPATCH:
        spec_dir = Path(spec_root) / ".spec-workflow" / "specs" / spec_name
        doc_path = spec_dir / f"{args.doc}.md"
        if doc_path.is_file():
            antipattern_result = workspace_validation.run_antipattern_lint(
                args.doc, doc_path, project_path=Path(spec_root),
            )
            combined = specs.merge_validation_results(
                combined, antipattern_result,
            )
    traceability_errors: list[dict] = []
    if args.doc == "tasks":
        traceability_errors = _traceability_errors(spec_root, spec_name)
    return _ValidateResult(shape=combined, traceability=traceability_errors)


def main() -> None:
    parser = cli.strict_parser("Validate workspace spec")
    cli.add_workspace_arg(parser)
    cli.target_argument(parser, family="workspace-target")
    parser.add_argument(
        "--doc",
        choices=list(DOC_PHASES),
        help="Validate only one document type (phase-aware mode)",
    )
    parser.add_argument(
        "--tracker-root",
        help=(
            "Coordinator workspace root (absolute path, or sentinel "
            "'coordinator' / 'workspace'). Required to enable auto "
            "docStatus update on success. Plain '.' is rejected — pick "
            "an absolute path or a sentinel so the resolution survives "
            "the --workspace chdir boundary."
        ),
    )
    parser.add_argument(
        "--tracker-target", default=None,
        help=(
            "Workspace tracker target as `<feature>/<repo-id>` "
            "(required with --tracker-root for auto docStatus update)"
        ),
    )

    args = parser.parse_args()
    ctx = cli.resolve_context(args, needs=("target", "workspace", "repo_id"))
    feature: "str | None" = None
    repo_id: "str | None" = None
    if args.tracker_target:
        feature, repo_id = split_workspace_target(args.tracker_target)
    root = cli.resolve_workspace_root(args)
    resolution = _resolve_spec_dir(root, args, feature, repo_id)
    spec_root = resolution.spec_root
    spec_name = resolution.spec_name
    feature = resolution.feature
    repo_id = resolution.repo_id

    result = _validate(spec_root, spec_name, args)
    combined = result.shape
    traceability_errors = result.traceability
    shape_errors = list(combined["errors"])
    has_errors = bool(shape_errors) or bool(traceability_errors)

    data: dict = {
        "specName": spec_name,
        "valid": not has_errors,
        "shape_errors": shape_errors,
        "traceability_errors": traceability_errors,
        "errors": shape_errors + traceability_errors,
        "warnings": combined["warnings"],
    }

    if has_errors:
        output.error(
            (
                f"Validation failed: {len(shape_errors)} shape error(s), "
                f"{len(traceability_errors)} traceability gap(s)"
            ),
            context=json.dumps(data, indent=2),
        )

    if feature and repo_id and args.doc:
        outcome = _tracker_update_outcome(
            args=args, feature=feature, repo_id=repo_id, doc=args.doc,
        )
        if outcome.kind == "ok":
            data.update(outcome.payload)
        else:
            data.setdefault("advisories", []).append(outcome.payload)

    output.success(
        data,
        f"Validation passed for {args.spec_name}",
        ctx=ctx,
        resolved_from=dict(ctx.resolved_from),
        handoffs=handoffs.handoffs_for(
            handoffs.current_script_id(), ctx,
        ),
    )


if __name__ == "__main__":
    cli.run_main(main)
