#!/usr/bin/env python3
"""Create a discovery project folder with default manifest.

Usage: init-project.py --name NAME
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

from sdd_core import cli, handoffs, output, paths
from sdd_core.text import KEBAB_RE
from sdd_core.time import ts_now

# Mirrors workflow-graph.json `sdd-create-discovery.context_needs`.
__sdd_context_needs__ = ("target", "workspace")

DEFAULT_MANIFEST = {
    "schemaVersion": "1.0.0",
    "status": "draft",
    "owner": "",
    "specs": [],
    "artifacts": [],
}


def main() -> None:
    parser = cli.strict_parser("Create discovery project")
    parser.add_argument("--name", required=True, help="Project name (kebab-case)")
    args = parser.parse_args()
    # Treat --name as the discovery target so the resolver records it
    # alongside the workspace in resolved_from provenance.
    if not getattr(args, "target", None):
        args.target = args.name
    ctx = cli.resolve_context(args, needs=__sdd_context_needs__)

    if not KEBAB_RE.match(args.name):
        output.error(
            f"Invalid project name: {args.name}",
            hint="Use kebab-case (e.g., user-onboarding, payment-flow-v2)",
        )

    root = paths.require_workflow_root()
    project_dir = paths.discovery_dir(root, args.name)
    manifest_path = project_dir / "manifest.json"

    if manifest_path.is_file():
        validate_cmd = (
            f".spec-workflow/sdd discovery/validate-manifest.py "
            f"--name {args.name}"
        )
        output.error(
            f"Discovery project '{args.name}' already exists",
            hint=f"Run: {validate_cmd}",
            next_action_command=validate_cmd,
        )

    if project_dir.is_dir() and any(project_dir.iterdir()):
        output.warn(
            f"Reclaiming partially-initialised directory for discovery "
            f"project '{args.name}' (manifest missing)."
        )

    project_dir.mkdir(parents=True, exist_ok=True)

    now = ts_now()
    manifest = {**DEFAULT_MANIFEST, "name": args.name, "createdAt": now, "updatedAt": now}
    manifest_path = str(project_dir / "manifest.json")
    output.atomic_write_json(manifest_path, manifest, verify_key="name")

    output.success(
        {"projectDir": str(project_dir), "manifest": manifest},
        f"Created discovery project '{args.name}'",
        ctx=ctx,
        resolved_from=dict(ctx.resolved_from),
        handoffs=handoffs.handoffs_for(handoffs.current_script_id(), ctx),
    )


if __name__ == "__main__":
    cli.run_main(main)
