#!/usr/bin/env python3
"""List every shim command registered via ``__sdd_manifest__``.

Walks the sibling script groups (``spec/``, ``review/``, ``util/`` …)
and emits a grouped registry so agents can answer "which groups /
scripts are available via ``.spec-workflow/sdd``?" without hunting
through the filesystem. The payload complements ``util/script-index``
(which indexes ``util/`` + ``review/`` only); ``list-commands`` covers
every group so the shim dispatcher's unresolved-command error can
direct agents here.

Usage:
  list-commands.py                 # every group (default)
  list-commands.py --group review  # filter to one group
  list-commands.py --all           # explicit full registry

Exit code: 0 always (result in JSON envelope).
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import ast
from pathlib import Path

from sdd_core import cli, output
from sdd_core.command_templates import available_scripts


__sdd_manifest__ = {
    "summary": "List every shim command grouped by script directory",
    "verbs": [
        "(no args)",
        "--all",
        "--group <group>",
    ],
    "aliases": {},
    "flags": ["--group", "--all"],
}


_HERE = Path(__file__).resolve().parent.parent


def _extract_manifest(tree: ast.Module) -> dict | None:
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name) or target.id != "__sdd_manifest__":
            continue
        if not isinstance(node.value, ast.Dict):
            continue
        try:
            return ast.literal_eval(node.value)
        except (ValueError, SyntaxError):
            return None
    return None


def _script_summary(path: Path) -> str:
    try:
        source = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ""
    manifest = _extract_manifest(tree) or {}
    if manifest.get("summary"):
        return str(manifest["summary"])
    doc = ast.get_docstring(tree) or ""
    first = doc.strip().splitlines()[0] if doc.strip() else ""
    return first.rstrip(".")


def _collect() -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for rel in available_scripts(str(_HERE)):
        group, _, filename = rel.partition("/")
        abs_path = _HERE / group / filename
        summary = _script_summary(abs_path)
        groups.setdefault(group, []).append({
            "script": rel,
            "summary": summary,
        })
    return groups


def main() -> None:
    parser = cli.strict_parser(__doc__)
    parser.add_argument(
        "--group", default=None,
        help="Filter to a single script group (e.g. review, util).",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Emit every group (default).",
    )
    args = parser.parse_args()

    grouped = _collect()
    if args.group:
        grouped = {k: v for k, v in grouped.items() if k == args.group}

    payload_groups = [
        {"name": name, "commands": cmds}
        for name, cmds in sorted(grouped.items())
    ]
    total = sum(len(g["commands"]) for g in payload_groups)
    output.success(
        {"groups": payload_groups},
        f"{total} command(s) across {len(payload_groups)} group(s)",
    )


if __name__ == "__main__":
    cli.run_main(main)
