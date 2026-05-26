#!/usr/bin/env python3
"""Extract delegation context for a target repo from the coordination spec.

Usage: .spec-workflow/sdd workspace/extract-delegation.py --workspace <path> --target <feature>/<repo-id>
"""
import _bootstrap  # noqa: F401

from sdd_core import cli, handoffs, output, delegation, workspace
from sdd_core.workspace_phase import DOC_PHASES

# Mirrors workflow-graph.json `sdd-workspace-create-spec.context_needs`.
__sdd_context_needs__ = ("target", "workspace", "repo_id")


def main() -> None:
    parser = cli.workspace_parser("Extract delegation context")
    parser.add_argument(
        "--doc-scope",
        choices=list(DOC_PHASES),
        help="Limit context extraction to one document type (fewer file reads)",
    )
    args = parser.parse_args()
    ctx = cli.resolve_context(args, needs=("target", "workspace", "repo_id"))
    if not args.repo_id:
        output.error(
            "--target must include the repo id (`<feature>/<repo-id>`)",
            hint="e.g. --target my-feature/api-svc",
        )
    root = cli.resolve_workspace_root(args)

    manifest = workspace.require_manifest(
        root, args.feature, hint="Create a coordination-manifest.json first",
    )

    context = delegation.extract_delegation_context(
        root, args.feature, args.repo_id,
        manifest=manifest,
        doc_scope=getattr(args, "doc_scope", None),
    )

    scope = getattr(args, "doc_scope", None)
    warnings = []
    if context.get("repoType") != "coordinator":
        if not context.get("role"):
            warnings.append(f"No role defined for repo '{args.repo_id}' in manifest")
        if (scope is None or scope == "requirements") and not context.get("requirements_subset"):
            warnings.append(
                f"No requirements subset found for repo '{args.repo_id}' in coordination spec. "
                "This is normal when requirements are cross-cutting rather than per-repo. "
                "Use the repo role description and full coordination requirements as context instead."
            )
        if (scope is None or scope == "design") and not context.get("design_section"):
            warnings.append(f"No design section found for repo '{args.repo_id}' in coordination spec")
        if (scope is None or scope == "design") and not context.get("api_contracts"):
            warnings.append(f"No API contracts found for repo '{args.repo_id}' in coordination spec")
        if (scope is None or scope == "tasks") and not context.get("depends_on_context"):
            warnings.append(f"No dependency context found for repo '{args.repo_id}' in coordination tasks")

    data = dict(context)
    if warnings:
        data["advisories"] = [
            {"name": "delegation-warning", "level": "warn", "message": w}
            for w in warnings
        ]
    output.success(
        data,
        f"Delegation context extracted for {args.repo_id}",
        ctx=ctx,
        resolved_from=dict(ctx.resolved_from),
        handoffs=handoffs.handoffs_for(handoffs.current_script_id(), ctx),
    )


if __name__ == "__main__":
    cli.run_main(main)
