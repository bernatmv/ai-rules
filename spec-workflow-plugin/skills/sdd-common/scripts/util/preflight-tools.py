#!/usr/bin/env python3
"""Emit the deferred-tool preload envelope for the active harness.

Claude Code lists ``AskUserQuestion`` / ``TaskCreate`` / ``TaskUpdate``
/ ``TodoWrite`` / ``WebFetch`` in its deferred-tools index but the
schemas are not callable until the agent runs ``ToolSearch``. This
script surfaces the exact preload command next to a stable envelope so
agents and the workspace health facade never hand-roll the reminder.

Usage:
  .spec-workflow/sdd util/preflight-tools.py --workspace .
  .spec-workflow/sdd util/preflight-tools.py --check-only
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

from sdd_core import cli, output, paths
from sdd_core.harness import load_adapter
from sdd_core.transient_state import (
    load_deferred_tool_preload,
    preload_tool_search_command,
)


__sdd_manifest__ = {
    "summary": "Emit the deferred-tool preload envelope for the active harness",
    "verbs": [
        "(no flags) — emit the preload envelope",
        "--check-only — exit 0 iff preload is already recorded",
        "--skill <name> — intersect with the skill's allowed-tools frontmatter",
    ],
    "flags": ["--workspace", "--check-only", "--skill"],
}


def _read_allowed_tools(project_path: str, skill: str) -> "tuple[str, ...] | None":
    """Read ``allowed-tools`` from the named skill's SKILL.md frontmatter.

    Returns ``None`` when the SKILL.md is absent or does not declare an
    ``allowed-tools`` field. The advisory then keeps the harness-default
    deferred-tool list rather than filtering it down.
    """
    from pathlib import Path

    candidates = (
        Path(project_path) / ".cursor" / "skills" / skill / "SKILL.md",
        Path(project_path) / ".claude" / "skills" / skill / "SKILL.md",
    )
    skill_md = next((c for c in candidates if c.is_file()), None)
    if skill_md is None:
        return None
    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    try:
        _, frontmatter, _ = text.split("---", 2)
    except ValueError:
        return None
    allowed: list[str] = []
    in_block = False
    for line in frontmatter.splitlines():
        stripped = line.strip()
        if stripped.startswith("allowed-tools:") or stripped.startswith("allowed_tools:"):
            value = stripped.split(":", 1)[1].strip()
            if value.startswith("[") and value.endswith("]"):
                inner = value[1:-1]
                allowed = [t.strip().strip("'\"") for t in inner.split(",") if t.strip()]
                in_block = False
                break
            if value:
                allowed = [t.strip() for t in value.split(",") if t.strip()]
                in_block = False
                break
            in_block = True
            continue
        if in_block:
            if stripped.startswith("- "):
                allowed.append(stripped[2:].strip().strip("'\""))
                continue
            if stripped and not stripped.startswith("#"):
                in_block = False
    return tuple(allowed) if allowed else None


def _emit_envelope(
    adapter_name: str, tools: tuple[str, ...], *, recorded: bool,
) -> None:
    if not tools:
        output.success(
            {"harness": adapter_name, "deferred_tools": []},
            "No preload needed on this harness",
        )
        return

    data = {
        "harness": adapter_name,
        "deferred_tools": list(tools),
        "next_action_command": preload_tool_search_command(tools),
        "already_preloaded": recorded,
    }
    if recorded:
        output.success(
            data, f"Deferred-tool preload already recorded ({len(tools)} tool(s))",
        )
        return
    output.success(
        data, f"Preload {len(tools)} deferred tool schema(s) before proceeding",
    )


def main() -> None:
    parser = cli.strict_parser(__doc__)
    parser.add_argument(
        "--check-only", action="store_true", dest="check_only",
        help="Exit without the envelope when the preload is already recorded.",
    )
    parser.add_argument(
        "--skill", default=None,
        help=(
            "Filter deferred-tool list by the named skill's allowed-tools "
            "frontmatter (e.g. --skill sdd-common). When set, only tools "
            "that the skill declares are surfaced."
        ),
    )
    args = parser.parse_args()

    project_path = paths.resolve_project_path(args)
    adapter = load_adapter(project_path)
    tools = tuple(adapter.deferred_tools())
    if args.skill:
        allowed = _read_allowed_tools(project_path, args.skill)
        if allowed is not None:
            tools = tuple(t for t in tools if t in allowed)
    recorded = load_deferred_tool_preload(project_path, adapter.name, tools)

    if args.check_only:
        if not tools or recorded:
            output.success(
                {
                    "harness": adapter.name,
                    "deferred_tools": list(tools),
                    "already_preloaded": True,
                },
                "Deferred-tool preload satisfied",
            )
            return
        output.warn(
            f"Deferred-tool preload pending: {', '.join(tools)}",
        )
        output.result(
            {
                "harness": adapter.name,
                "deferred_tools": list(tools),
                "already_preloaded": False,
                "next_action_command": preload_tool_search_command(tools),
            },
            "Deferred-tool preload pending",
            exit_code=1,
        )
        return

    _emit_envelope(adapter.name, tools, recorded=recorded)


if __name__ == "__main__":
    cli.run_main(main)
