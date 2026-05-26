#!/usr/bin/env python3
"""Initialize .spec-workflow/ directory structure with default templates.

Usage: .spec-workflow/sdd workspace/init.py [--workspace PATH]
"""
import _bootstrap  # noqa: F401

from pathlib import Path
from sdd_core import cli, handoffs, output, paths, preflight_state
from sdd_core.paths import WORKFLOW_DIR
from sdd_core.shim import ensure_shim
from sdd_core.templates import sync_defaults_to_workspace, sync_user_templates_readme

# Workspace-only shim: no target / repo_id / phase consumed.
__sdd_context_needs__ = ("workspace",)

DIRS = ["approvals", "archive/specs", "specs", "steering", "templates", "user-templates"]


def main() -> None:
    parser = cli.strict_parser("Initialize .spec-workflow/ workspace")
    args = parser.parse_args()
    ctx = cli.resolve_context(args, needs=("workspace",))

    root = Path(paths.resolve_project_path(args)).resolve()
    if not root.is_dir():
        output.error(f"Invalid project path: {root}", exit_code=1)

    workflow_root = root / WORKFLOW_DIR
    created, skipped = [], []

    for d in DIRS:
        dp = workflow_root / d
        if dp.is_dir():
            skipped.append(d)
        else:
            dp.mkdir(parents=True, exist_ok=True)
            created.append(d)

    shim_action = ensure_shim(workflow_root)
    if shim_action:
        created.append(f"sdd (shim {shim_action})")

    init_advisories: list[dict] = []
    sync_result = sync_defaults_to_workspace(root)
    for name in sync_result.copied:
        created.append(f"templates/{name}")
    for warning in sync_result.warnings:
        init_advisories.append({"name": "template-sync-warning", "level": "warn", "message": warning})
    for failure in sync_result.failed:
        init_advisories.append({"name": "template-sync-failed", "level": "warn", "message": f"Template sync failed: {failure}"})

    sync_user_templates_readme(workflow_root, created, skipped, warn_callback=lambda msg: init_advisories.append({"name": "readme-sync-warning", "level": "warn", "message": msg}))

    # Init is the lifecycle boundary where ``harness.json`` is expected;
    # the safe-default loader branch never persists, so persist here.
    from sdd_core.harness import load_adapter
    from sdd_core.harness.loader import harness_state_path, persist_state

    adapter = load_adapter(str(root))
    persist_state(adapter.name, str(root))
    if Path(harness_state_path(str(root))).is_file():
        created.append(".sdd-state/harness.json")
    preflight_state.mark_resolved("deferred_tools_preload", workspace=str(root))

    success_data: dict = {"created": created, "skipped": skipped}
    if init_advisories:
        success_data["advisories"] = init_advisories
    output.success(
        success_data,
        f"Workspace initialized at {workflow_root}",
        ctx=ctx,
        resolved_from=dict(ctx.resolved_from),
        handoffs=handoffs.handoffs_for(handoffs.current_script_id(), ctx),
    )


if __name__ == "__main__":
    cli.run_main(main)
