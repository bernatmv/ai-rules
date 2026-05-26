#!/usr/bin/env python3
"""Mark a pre-flight advisory resolved so the next phase unblocks.

Usage:
  .spec-workflow/sdd workspace/resolve-advisory.py --name <advisory>
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

from pathlib import Path

from sdd_core import cli, output, preflight_state, session
from sdd_core.command_templates import build_ensure_healthy_command

__sdd_context_needs__ = ("workspace",)


def main() -> None:
    parser = cli.strict_parser("Resolve a pre-flight advisory by name")
    parser.add_argument("--name", required=True, help="Advisory name to resolve")
    args = parser.parse_args()
    workspace = str(cli.resolve_workspace_root(args))
    session_id = session.get_or_create_session_id(Path(workspace))
    outcome = preflight_state.mark_resolved(
        args.name, workspace=workspace, session_id=session_id,
    )
    if outcome.mutated:
        output.success(
            {"name": args.name, "resolved": True},
            f"Advisory {args.name} marked resolved",
        )
        return

    if outcome.already_resolved:
        output.success(
            {"name": args.name, "resolved": True, "outcome": "already_resolved"},
            f"Advisory {args.name} already resolved (no change)",
        )
        return

    next_cmd = build_ensure_healthy_command(workspace_path=workspace)
    output.miss(
        {"name": args.name, "resolved": False, "outcome": "not_found"},
        f"Advisory {args.name} not found in preflight state",
        next_action_command=next_cmd,
        hint=(
            "Refresh advisories via workspace/ensure-healthy.py, "
            "then re-run this command if the advisory persists."
        ),
    )


if __name__ == "__main__":
    cli.run_main(main)
