#!/usr/bin/env python3
"""Workspace pre-flight fan-out across every repo in the coordination manifest.

Reads ``coordination-manifest.json::repos[].path`` for the workspace's
features and runs ``workspace/check-health.py`` once per repo *under one
parent process*. The harness sees a single tool call, removing the
cancelled-sibling cascade that N parallel shim invocations expose.

Usage:
    .spec-workflow/sdd workspace/preflight-all.py [--workspace PATH] \
                                                  [--target FEATURE] [--auto-fix]

Outputs a single JSON envelope with ``data.repos[]`` (per-repo summary)
and a top-level ``data.healthy`` boolean. ``--auto-fix`` is opt-in;
default is detect-only.
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import json
from pathlib import Path

from sdd_core import cli, handoffs, output, paths
from sdd_core.command_templates import build_workspace_preflight_all_command
from sdd_core.paths import (
    COORDINATION_MANIFEST_FILENAME,
    WORKFLOW_DIR,
    workspace_dir,
)
from sdd_core.subprocess_dispatch import run_dispatched

# Workspace-level fan-out: target is optional (filters fan-out by feature).
__sdd_context_needs__ = ("target", "workspace")

_AUTO_FIX_FLAG = "--auto-fix"


def _list_features(workspace_root: Path) -> list[str]:
    base = workspace_dir(workspace_root)
    if not base.is_dir():
        return []
    return sorted(
        d.name for d in base.iterdir()
        if d.is_dir() and (d / COORDINATION_MANIFEST_FILENAME).is_file()
    )


def _load_repos(workspace_root: Path, feature: str) -> list[dict]:
    manifest_path = (
        workspace_dir(workspace_root, feature) / COORDINATION_MANIFEST_FILENAME
    )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    repos = manifest.get("repos") or []
    return [r for r in repos if isinstance(r, dict) and r.get("path")]


def _run_check_health(repo_path: Path, *, auto_fix: bool) -> dict:
    extra = (_AUTO_FIX_FLAG,) if auto_fix else ()
    proc = run_dispatched(
        "workspace/check-health.py",
        *extra,
        project_path=repo_path,
    )
    raw = proc.stdout.strip() or proc.stderr.strip()
    try:
        envelope = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        envelope = {"status": "error", "error": "non-JSON output", "raw": raw}
    healthy = bool(envelope.get("data", {}).get("healthy"))
    return {
        "path": str(repo_path),
        "healthy": healthy,
        "envelope": envelope,
        "exit_code": proc.returncode,
    }


def main() -> None:
    parser = cli.strict_parser("Workspace pre-flight fan-out (all repos)")
    cli.target_argument(parser, family="workspace", required=False)
    parser.add_argument(
        _AUTO_FIX_FLAG, action="store_true",
        help=f"Pass {_AUTO_FIX_FLAG} to each check-health.py invocation",
    )
    args = parser.parse_args()
    ctx = cli.resolve_context(args, needs=("target", "workspace"))

    root = Path(paths.resolve_project_path(args)).resolve()
    workflow = root / WORKFLOW_DIR
    if not workflow.is_dir():
        output.error(
            f"No {WORKFLOW_DIR}/ directory found at {root}",
            hint="Run workspace/init.py first",
            next_action_command=".spec-workflow/sdd workspace/init.py --workspace .",
        )

    feature = getattr(args, "feature", "") or ""
    features = [feature] if feature else _list_features(root)
    if not features:
        output.miss(
            {
                "healthy": True,
                "repos": [],
                "next_action_command": build_workspace_preflight_all_command(
                    root, auto_fix=True,
                ),
            },
            "No workspace features with a coordination manifest found",
        )

    seen: set[str] = set()
    summaries: list[dict] = []
    for feature in features:
        repos = _load_repos(root, feature)
        if not repos:
            continue
        for repo in repos:
            repo_path = Path(repo["path"]).expanduser()
            key = str(repo_path.resolve()) if repo_path.exists() else str(repo_path)
            if key in seen:
                continue
            seen.add(key)
            summary = _run_check_health(repo_path, auto_fix=args.auto_fix)
            summary["id"] = repo.get("id") or repo.get("name") or key
            summary["feature"] = feature
            summaries.append(summary)

    healthy = all(s.get("healthy") for s in summaries) if summaries else True
    payload = {
        "healthy": healthy,
        "repos": summaries,
        "next_action_command": build_workspace_preflight_all_command(
            root, auto_fix=True,
        ),
    }

    if not summaries:
        output.miss(payload, "No repos resolved across the workspace manifests")

    if healthy:
        output.success(
            payload,
            f"Workspace healthy across {len(summaries)} repo(s)",
            ctx=ctx,
            resolved_from=dict(ctx.resolved_from),
            handoffs=handoffs.handoffs_for(handoffs.current_script_id(), ctx),
        )
    else:
        failing = [s["id"] for s in summaries if not s.get("healthy")]
        output.partial(
            payload,
            f"Workspace pre-flight: {len(failing)} repo(s) failing — {', '.join(failing)}",
        )


if __name__ == "__main__":
    cli.run_main(main)
