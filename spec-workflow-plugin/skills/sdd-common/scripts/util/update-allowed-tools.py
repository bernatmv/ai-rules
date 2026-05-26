#!/usr/bin/env python3
"""Update every SKILL.md frontmatter ``allowed-tools`` line from the
adapter-declared deferred-tool set.

The canonical allow-list is ``<STATIC_BASE> ∪
⋃ adapter.deferred_tools()`` over every registered adapter. The base
set covers tools every skill uses regardless of host (``Read Write
Edit Bash Agent AskQuestion``); deferred tools are harness-specific
schemas that each adapter advertises.

Skills whose SKILL.md carries ``user-invocable: false`` are treated as
internal references — they use the reduced base set only.

Usage:
  .spec-workflow/sdd util/update-allowed-tools.py            # rewrite in place
  .spec-workflow/sdd util/update-allowed-tools.py --check-only  # exit 1 on drift
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import re
from pathlib import Path

from sdd_core import cli, output, paths
from sdd_core.command_templates import build_shim_command
from sdd_core.harness import ADAPTERS

__sdd_manifest__ = {
    "summary": "Keep SKILL.md allowed-tools frontmatter in sync with adapters",
    "verbs": [
        "(no flags) — rewrite frontmatter in place",
        "--check-only — exit 1 on drift",
    ],
    "flags": ["--check-only", "--workspace"],
}


# Tools every user-invocable SKILL.md is expected to reach for,
# independent of host. Deferred tools (``AskUserQuestion`` etc.) are
# added per-adapter so adding a new harness is one adapter edit, not a
# scan over every SKILL.md.
_STATIC_BASE = ("Read", "Write", "Edit", "Bash", "Agent", "AskQuestion")
_INTERNAL_BASE = ("Read", "Write", "Edit", "Bash", "Agent")

_ALLOWED_RE = re.compile(
    r"^(allowed-tools:)([^\n]*)$", re.MULTILINE,
)


def compute_allowed_tools(*, user_invocable: bool) -> list[str]:
    """Return the canonical tool list for a SKILL.md frontmatter."""
    if not user_invocable:
        return list(_INTERNAL_BASE)
    merged: set[str] = set(_STATIC_BASE)
    for adapter in ADAPTERS.values():
        for tool in adapter.deferred_tools():
            merged.add(tool)
    base_order = list(_STATIC_BASE)
    extras = sorted(merged - set(_STATIC_BASE))
    return base_order + extras


def _is_user_invocable(text: str) -> bool:
    return "user-invocable: false" not in text.split("\n---", 1)[0]


def _apply(path: Path, *, check_only: bool) -> tuple[bool, str]:
    """Return ``(changed, replacement_line)``; writes in place unless check-only."""
    text = path.read_text(encoding="utf-8")
    tools = compute_allowed_tools(user_invocable=_is_user_invocable(text))
    replacement = f"allowed-tools: {' '.join(tools)}"
    match = _ALLOWED_RE.search(text)
    if not match:
        return False, replacement
    current = match.group(0)
    if current == replacement:
        return False, replacement
    if not check_only:
        new_text = text[:match.start()] + replacement + text[match.end():]
        path.write_text(new_text, encoding="utf-8")
    return True, replacement


def main() -> None:
    parser = cli.strict_parser(__doc__)
    parser.add_argument(
        "--check-only", action="store_true", dest="check_only",
        help="Exit 1 when any frontmatter drifts from the canonical set.",
    )
    args = parser.parse_args()

    try:
        from sdd_core.harness import try_load_adapter
        harness_name = try_load_adapter().name
    except Exception:  # noqa: BLE001 — advisory probe only
        harness_name = None
    skills_root = Path(paths.find_skills_root(harness_name=harness_name))
    drift: list[dict] = []
    rewrote: list[str] = []
    for skill_md in sorted(skills_root.glob("*/SKILL.md")):
        changed, expected = _apply(skill_md, check_only=args.check_only)
        if changed:
            entry = {"file": str(skill_md), "expected": expected}
            if args.check_only:
                drift.append(entry)
            else:
                rewrote.append(str(skill_md))

    if args.check_only and drift:
        output.error(
            f"{len(drift)} SKILL.md allowed-tools drift(s)",
            hint="\n".join(
                f"{d['file']} — expected: {d['expected']}" for d in drift
            ),
            next_action_command=build_shim_command("util/update-allowed-tools.py"),
        )
        return

    output.success(
        {"checked": [str(p) for p in skills_root.glob("*/SKILL.md")],
         "rewrote": rewrote,
         "drift": drift},
        (
            f"allowed-tools check clean"
            if not rewrote
            else f"rewrote {len(rewrote)} SKILL.md allowed-tools line(s)"
        ),
    )


if __name__ == "__main__":
    cli.run_main(main)
