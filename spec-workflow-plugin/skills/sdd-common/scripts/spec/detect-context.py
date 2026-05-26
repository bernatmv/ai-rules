#!/usr/bin/env python3
"""Detect whether a spec is standalone or part of a workspace.

Usage: detect-context.py <spec-name> [--workspace PATH]

Checks (in order):
1. Does .spec-workflow/workspace/{spec-name}/ exist with a manifest?
   → context: "coordination" (this spec IS the workspace coordination spec)
2. For any workspace manifest, does it list this spec-name as a repos[].subSpec?
   → context: "sub-spec" (this spec is a delegation target)
3. Neither?
   → context: "standalone" (regular single-repo spec)

Output: JSON with context, approvalMode, feature, repoId fields.
All contexts exit 0 with structured JSON output.
"""

import _bootstrap  # noqa: F401

from pathlib import Path

from sdd_core import cli, handoffs, output, paths
from sdd_core.paths import COORDINATION_MANIFEST_FILENAME

# Mirrors workflow-graph.json `sdd-create-spec.context_needs`.
__sdd_context_needs__ = ("target", "workspace")


def _standalone_payload() -> dict:
    return {
        "context": "standalone",
        "approvalMode": "sequential",
        "feature": None,
        "repoId": None,
    }


def _resolve_prd_metadata(spec_name: str, root: Path) -> dict:
    """Resolve PRD path + lookup result for ``spec_name``.

    Same lookup used by ``launch`` — calling through
    ``discovery/shared`` keeps one locator even when callers sit on
    opposite ends of the pipeline. Emits a ``next_action_command``
    remediation when a discovery project exists but no PRD is linked,
    so the agent has a literal recovery command on hand.
    """
    from discovery.shared import (
        build_add_spec_link_command,
        find_prd_for_spec,
        get_discovery_project_names,
    )

    root_path = Path(root)
    backlinked = find_prd_for_spec(spec_name, root_path)
    if backlinked:
        return {
            "prd_file_path": backlinked,
            "prd_lookup_result": "backlink",
        }

    direct_dir = root_path / ".spec-workflow" / "discovery" / spec_name
    if direct_dir.is_dir():
        # Same-name fallback kept so discovery-category launches still
        # resolve their PRD when the spec hasn't been back-linked yet.
        from discovery.shared import find_prd_files

        prd_files = find_prd_files(direct_dir)
        if prd_files:
            return {
                "prd_file_path": (
                    f".spec-workflow/discovery/{spec_name}/{prd_files[0]}"
                ),
                "prd_lookup_result": "direct",
            }

    result: dict = {
        "prd_file_path": None,
        "prd_lookup_result": "none",
    }
    projects = get_discovery_project_names(root_path)
    if projects:
        result["prd_lookup_warning"] = (
            f"No discovery project linked to spec '{spec_name}'. "
            f"Existing discovery project(s): {', '.join(projects)}."
        )
        result["prd_lookup_next_action_command"] = build_add_spec_link_command(
            project="<project>", spec=spec_name, relationship="prd",
        )
        # Emit an ``ask_question_payload`` listing each candidate
        # project plus a "skip linking" option so the agent can feed
        # it straight to ``AskQuestion`` — the ``<project>`` placeholder
        # in ``prd_lookup_next_action_command`` otherwise requires
        # open-ended judgement the agent shouldn't improvise.
        result["prd_lookup_ask_question_payload"] = (
            _build_prd_link_ask_question_payload(spec_name, projects)
        )
    return result


def _build_prd_link_ask_question_payload(
    spec_name: str, projects: list[str],
) -> dict:
    """Shape an ``AskQuestion`` payload for PRD-link project selection.

    Mirrors the shape ``check-status.py --suggest-name`` uses so the
    agent can route both surfaces through one mental model.
    """
    from discovery.shared import build_add_spec_link_command
    options = []
    for idx, project in enumerate(projects):
        options.append({
            "id": f"link-{idx}",
            "label": (
                f"Link discovery project '{project}' as PRD for "
                f"'{spec_name}'"
            ),
            "next_action_command": build_add_spec_link_command(
                project=project, spec=spec_name, relationship="prd",
            ),
            "project": project,
        })
    options.append({
        "id": "skip-linking",
        "label": "Skip PRD linking for now (can be linked later)",
        "next_action_command": None,
        "project": None,
    })
    return {
        "user_question_prompt": (
            f"Which discovery project should be linked as the PRD for "
            f"spec '{spec_name}'?"
        ),
        "questions": [
            {
                "id": "prd-link-selection",
                "prompt": (
                    f"Which discovery project should be linked as the "
                    f"PRD for spec '{spec_name}'?"
                ),
                "options": options,
            }
        ],
    }


def detect_context(spec_name: str, root):
    ws_base = root / paths.WORKFLOW_DIR / "workspace"

    coord_dir = ws_base / spec_name
    manifest_path = coord_dir / COORDINATION_MANIFEST_FILENAME
    if manifest_path.is_file():
        return {
            "context": "coordination",
            "approvalMode": "batch",
            "feature": spec_name,
            "repoId": None,
        }

    if ws_base.is_dir():
        for feature_dir in ws_base.iterdir():
            if not feature_dir.is_dir():
                continue
            m_path = feature_dir / COORDINATION_MANIFEST_FILENAME
            if not m_path.is_file():
                continue
            manifest = output.safe_read_json(str(m_path))
            if manifest is None:
                continue
            for repo in manifest.get("repos", []):
                if repo.get("subSpec") == spec_name:
                    return {
                        "context": "sub-spec",
                        "approvalMode": "batch",
                        "feature": manifest.get("feature"),
                        "repoId": repo.get("id"),
                    }

    return _standalone_payload()


def main():
    parser = cli.strict_parser("Detect spec context (standalone vs workspace)")
    parser.add_argument("spec_name_pos", nargs="?", default=None, help="Spec name to check")
    cli.target_argument(parser, family="spec", required=False)
    args = parser.parse_args()
    args.spec_name = args.spec_name or args.spec_name_pos
    if not args.spec_name:
        output.error("Spec name is required (positional or --target)")
    ctx = cli.resolve_context(args, needs=__sdd_context_needs__)

    def _emit(payload: dict, msg: str) -> None:
        output.success(
            payload,
            msg,
            ctx=ctx,
            resolved_from=dict(ctx.resolved_from),
            handoffs=handoffs.handoffs_for(handoffs.current_script_id(), ctx),
        )

    try:
        root = paths.find_workflow_root(paths.resolve_project_path(args))
    except FileNotFoundError:
        result = _standalone_payload()
        _emit(result, "No .spec-workflow/ found — standalone context assumed")
        return

    result = detect_context(args.spec_name, root)
    result.update(_resolve_prd_metadata(args.spec_name, root))
    _emit(result, f"Context: {result['context']} → {result['approvalMode']} approval mode")


if __name__ == "__main__":
    cli.run_main(main)
