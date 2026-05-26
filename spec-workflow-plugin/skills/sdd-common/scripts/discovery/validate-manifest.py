#!/usr/bin/env python3
"""Validate a discovery manifest against schema constraints.

Usage: validate-manifest.py --name NAME
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

from sdd_core import cli, handoffs, output, paths
from discovery.shared import (
    REQUIRED_ARTIFACT_FIELDS,
    REQUIRED_MANIFEST_FIELDS,
    REQUIRED_SPEC_FIELDS,
    VALID_ARTIFACT_STATUSES,
    VALID_PROJECT_STATUSES,
)

# Mirrors workflow-graph.json `sdd-create-discovery.context_needs`.
__sdd_context_needs__ = ("target", "workspace")


def main() -> None:
    parser = cli.strict_parser("Validate discovery manifest")
    parser.add_argument("--name", required=True, help="Project name")
    args = parser.parse_args()
    if not getattr(args, "target", None):
        args.target = args.name
    ctx = cli.resolve_context(args, needs=__sdd_context_needs__)

    root = paths.require_workflow_root()
    manifest_path = paths.discovery_dir(root, args.name) / "manifest.json"
    data = output.safe_read_json(str(manifest_path))

    if data is None:
        output.error(f"Manifest not found for project '{args.name}'")

    errors: list[str] = []

    for field in REQUIRED_MANIFEST_FIELDS:
        if field not in data or not data[field]:
            errors.append(f"Missing required field: {field}")

    if data.get("status") not in VALID_PROJECT_STATUSES:
        errors.append(f"Invalid project status: {data.get('status')}")

    seen_files: set[str] = set()
    for i, artifact in enumerate(data.get("artifacts", [])):
        for f in REQUIRED_ARTIFACT_FIELDS:
            if f not in artifact:
                errors.append(f"Artifact [{i}]: missing field '{f}'")
        if artifact.get("status") not in VALID_ARTIFACT_STATUSES:
            errors.append(f"Artifact [{i}]: invalid status '{artifact.get('status')}'")
        fname = artifact.get("file", "")
        if fname in seen_files:
            errors.append(f"Duplicate artifact file: {fname}")
        seen_files.add(fname)

    seen_links: set[tuple[str, str]] = set()
    for i, spec in enumerate(data.get("specs", [])):
        for f in REQUIRED_SPEC_FIELDS:
            if f not in spec:
                errors.append(f"Spec link [{i}]: missing field '{f}'")
        key = (spec.get("name", ""), spec.get("relationship", ""))
        if key in seen_links:
            errors.append(f"Duplicate spec link: {key[0]} ({key[1]})")
        seen_links.add(key)

    if errors:
        output.error(
            f"Manifest validation failed ({len(errors)} error(s))",
            hint="; ".join(errors),
        )

    output.success(
        {
            "valid": True,
            "artifactCount": len(data.get("artifacts", [])),
            "specLinkCount": len(data.get("specs", [])),
        },
        "Manifest is valid",
        ctx=ctx,
        resolved_from=dict(ctx.resolved_from),
        handoffs=handoffs.handoffs_for(handoffs.current_script_id(), ctx),
    )


if __name__ == "__main__":
    cli.run_main(main)
