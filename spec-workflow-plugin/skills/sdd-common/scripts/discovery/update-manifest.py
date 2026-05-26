#!/usr/bin/env python3
"""Read-modify-write operations on a discovery manifest.

Usage:
  update-manifest.py --name NAME add-artifact --file FILE
  update-manifest.py --name NAME add-spec-link --spec SPEC --relationship REL
  update-manifest.py --name NAME set-artifact-status --file FILE --status STATUS
  update-manifest.py --name NAME set-project-status --status STATUS
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import argparse
from pathlib import Path

from sdd_core import cli, handoffs, output, paths
from sdd_core.context import WorkflowContext
from sdd_core.time import ts_now
from discovery.shared import (
    VALID_ARTIFACT_STATUSES,
    VALID_PROJECT_STATUSES,
    VALID_RELATIONSHIPS,
    detect_artifact_type as _detect_type,
)

# Mirrors workflow-graph.json `sdd-create-discovery.context_needs`.
__sdd_context_needs__ = ("target", "workspace")


def _emit(ctx: WorkflowContext, payload: dict, msg: str) -> None:
    output.success(
        payload,
        msg,
        ctx=ctx,
        resolved_from=dict(ctx.resolved_from),
        handoffs=handoffs.handoffs_for(handoffs.current_script_id(), ctx),
    )


def _load_manifest(root: Path, name: str) -> tuple[Path, dict]:
    manifest_path = paths.discovery_dir(root, name) / "manifest.json"
    data = output.safe_read_json(str(manifest_path))
    if data is None:
        output.error(
            f"Discovery project '{name}' not found",
            hint=f"Run: .spec-workflow/sdd discovery/init-project.py --name {name}",
        )
    return manifest_path, data


def _save_manifest(path: Path, data: dict) -> None:
    data["updatedAt"] = ts_now()
    output.atomic_write_json(str(path), data, verify_key="updatedAt")


def _add_artifact(manifest_path: Path, data: dict, args: argparse.Namespace, ctx: WorkflowContext) -> None:
    project_dir = manifest_path.parent
    file_path = project_dir / args.file
    if not file_path.exists():
        available = [f.name for f in project_dir.glob("*.md")]
        output.error(
            f"File '{args.file}' not found in project folder",
            hint=f"Available .md files: {', '.join(available) or '(none)'}",
        )

    existing_files = {a["file"] for a in data.get("artifacts", [])}
    if args.file in existing_files:
        output.error(f"Artifact '{args.file}' is already registered", hint="No duplicate added")

    detected_type = _detect_type(args.file)
    data.setdefault("artifacts", []).append({
        "file": args.file,
        "type": detected_type,
        "status": "draft",
    })
    _save_manifest(manifest_path, data)
    _emit(
        ctx,
        {"file": args.file, "type": detected_type, "status": "draft"},
        f"Registered '{args.file}' as '{detected_type}'",
    )


def _add_spec_link(manifest_path: Path, data: dict, args: argparse.Namespace, ctx: WorkflowContext) -> None:
    if args.relationship not in VALID_RELATIONSHIPS:
        output.error(
            f"Invalid relationship: {args.relationship}",
            hint=f"Valid values: {', '.join(sorted(VALID_RELATIONSHIPS))}",
        )

    existing = {(s["name"], s["relationship"]) for s in data.get("specs", [])}
    if (args.spec, args.relationship) in existing:
        output.error(
            f"Spec link '{args.spec}' ({args.relationship}) already exists",
            hint="No duplicate added",
        )

    data.setdefault("specs", []).append({"name": args.spec, "relationship": args.relationship})
    _save_manifest(manifest_path, data)
    _emit(
        ctx,
        {"spec": args.spec, "relationship": args.relationship},
        f"Linked spec '{args.spec}' ({args.relationship})",
    )


def _set_artifact_status(manifest_path: Path, data: dict, args: argparse.Namespace, ctx: WorkflowContext) -> None:
    if args.status not in VALID_ARTIFACT_STATUSES:
        output.error(
            f"Invalid artifact status: {args.status}",
            hint=f"Valid values: {', '.join(sorted(VALID_ARTIFACT_STATUSES))}",
        )

    for artifact in data.get("artifacts", []):
        if artifact["file"] == args.file:
            artifact["status"] = args.status

            artifacts = data.get("artifacts", [])
            if artifacts and all(a.get("status") == "approved" for a in artifacts):
                if data.get("status") != "approved":
                    data["status"] = "approved"
                    output.info("Auto-promoted project status to 'approved' (all artifacts approved)")

            _save_manifest(manifest_path, data)
            _emit(
                ctx,
                {"file": args.file, "status": args.status},
                f"Updated '{args.file}' status to '{args.status}'",
            )
            return

    registered = [a["file"] for a in data.get("artifacts", [])]
    output.error(
        f"Artifact '{args.file}' not found",
        hint=f"Registered artifacts: {', '.join(registered) or '(none)'}",
    )


def _set_project_status(manifest_path: Path, data: dict, args: argparse.Namespace, ctx: WorkflowContext) -> None:
    if args.status not in VALID_PROJECT_STATUSES:
        output.error(
            f"Invalid project status: {args.status}",
            hint=f"Valid values: {', '.join(sorted(VALID_PROJECT_STATUSES))}",
        )

    data["status"] = args.status
    _save_manifest(manifest_path, data)
    _emit(ctx, {"status": args.status}, f"Project status set to '{args.status}'")


def build_parser() -> argparse.ArgumentParser:
    """Return the argparse parser used by ``main``.

    Exposed so the shared ``discovery.shared.build_add_spec_link_command``
    helper (and its parity test) can round-trip the emitted CLI string
    through the same argparse that executes it at runtime — one
    authority for the command shape.
    """
    parser = cli.strict_parser("Update discovery manifest")
    parser.add_argument("--name", required=True, help="Project name")
    sub = parser.add_subparsers(dest="action", required=True)

    p_add = sub.add_parser("add-artifact")
    p_add.add_argument("--file", required=True)

    p_link = sub.add_parser("add-spec-link")
    p_link.add_argument("--spec", required=True)
    p_link.add_argument("--relationship", required=True)

    p_artifact_status = sub.add_parser("set-artifact-status")
    p_artifact_status.add_argument("--file", required=True)
    p_artifact_status.add_argument("--status", required=True)

    p_project_status = sub.add_parser("set-project-status")
    p_project_status.add_argument("--status", required=True)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    # Treat --name as the discovery target so the resolver records it
    # alongside the workspace in resolved_from provenance.
    if not getattr(args, "target", None):
        args.target = args.name
    ctx = cli.resolve_context(args, needs=__sdd_context_needs__)
    root = paths.require_workflow_root()
    manifest_path, data = _load_manifest(root, args.name)

    dispatch = {
        "add-artifact": _add_artifact,
        "add-spec-link": _add_spec_link,
        "set-artifact-status": _set_artifact_status,
        "set-project-status": _set_project_status,
    }
    dispatch[args.action](manifest_path, data, args, ctx)


if __name__ == "__main__":
    cli.run_main(main)
