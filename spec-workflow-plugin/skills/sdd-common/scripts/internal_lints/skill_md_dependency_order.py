#!/usr/bin/env python3
"""Lint SKILL.md Dependencies tables for read-before-run ordering.

Within any single Step group, every row whose ``Kind`` column is
``read`` MUST precede every row whose ``Kind`` is ``run``. The invariant
ensures the invocation contract (reference doc) is loaded before the
CLI that depends on it is executed — any other ordering risks a
fresh-turn ``run`` call that misinterprets its flag shape.

Usage:
  internal_lints/skill_md_dependency_order.py --path <SKILL.md>
  internal_lints/skill_md_dependency_order.py --all
  internal_lints/skill_md_dependency_order.py --baseline
  internal_lints/skill_md_dependency_order.py --path <SKILL.md> --suggest-fix
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import re
from pathlib import Path

from sdd_core import cli, output, paths
from sdd_core.skill_md_rules import load_raw_rules
from internal_lints._skill_md_lint_cli import (
    run_skill_md_lint, collect_skill_targets,
)

__sdd_manifest__ = {
    "summary": "SKILL.md Dependencies-table read-before-run ordering lint",
    "verbs": [
        "--path <skill.md>",
        "--all",
        "--baseline",
        "--suggest-fix",
    ],
    "flags": [
        "--path", "--all", "--baseline", "--suggest-fix", "--workspace",
    ],
}


_DEPS_HEADING_RE = re.compile(r"^##+\s+Dependencies\s*$", re.IGNORECASE)
_NEXT_HEADING_RE = re.compile(r"^##+\s+\S")
# Dependencies tables use a 3-column markdown table: | Step | File | Kind |.
# Each data row has three pipe-separated cells after the header separator.
_TABLE_ROW_RE = re.compile(r"^\s*\|(.+)\|\s*$")


def _extract_dependency_rows(text: str) -> list[tuple[int, str, str, str]]:
    """Return ``(line_idx, step, file_cell, kind)`` tuples for each data row.

    Walks from the ``## Dependencies`` heading to the next heading,
    skipping the header row and the markdown separator row. Returns an
    empty list when no Dependencies section exists.
    """
    lines = text.splitlines()
    in_deps = False
    rows: list[tuple[int, str, str, str]] = []
    header_seen = False
    separator_seen = False
    for idx, line in enumerate(lines):
        if not in_deps:
            if _DEPS_HEADING_RE.match(line):
                in_deps = True
                header_seen = False
                separator_seen = False
            continue
        if _NEXT_HEADING_RE.match(line) and not _DEPS_HEADING_RE.match(line):
            # Next section starts — stop scanning.
            break
        match = _TABLE_ROW_RE.match(line)
        if not match:
            continue
        cells = [cell.strip() for cell in match.group(1).split("|")]
        if len(cells) < 3:
            continue
        if not header_seen:
            header_seen = True
            continue
        if not separator_seen:
            # Typical ``|------|------|------|`` row — all cells are dashes.
            if all(set(cell) <= set("-: ") for cell in cells):
                separator_seen = True
                continue
            # Sometimes the table uses a non-standard separator — treat
            # as data anyway so we don't under-report.
            separator_seen = True
        step, file_cell, kind = cells[0], cells[1], cells[2].lower()
        if kind not in {"read", "run"}:
            # Ignore informational "All" / "Steps X–Y" rows missing a
            # valid kind — the schema allows non-kind rows for shared
            # references.
            continue
        rows.append((idx, step, file_cell, kind))
    return rows


def _ordering_violations(
    rows: list[tuple[int, str, str, str]], path: Path,
) -> list[dict]:
    """Return one violation per read-row that follows a run-row in the
    same Step group."""
    violations: list[dict] = []
    first_run_line_by_step: dict[str, int] = {}
    for line_idx, step, file_cell, kind in rows:
        if kind == "run":
            first_run_line_by_step.setdefault(step, line_idx)
            continue
        run_line = first_run_line_by_step.get(step)
        if run_line is not None:
            violations.append({
                "file": str(path),
                "line": line_idx + 1,
                "kind": "dependency_read_after_run",
                "step": step,
                "snippet": file_cell,
                "message": (
                    f"Dependencies row ({step}, kind=read) at line "
                    f"{line_idx + 1} follows a ``run`` row for the "
                    f"same Step at line {run_line + 1}. Reads must "
                    f"precede runs — load the contract before invoking "
                    f"the tool."
                ),
            })
    return violations


def lint_file(path: Path, rules: dict) -> list[dict]:
    """Return ordering violations for *path* — empty when no deps table."""
    cfg = (rules or {}).get("dependency_table_read_before_run") or {}
    if not cfg:
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    rows = _extract_dependency_rows(text)
    if not rows:
        return []
    return _ordering_violations(rows, path)


def _suggest_fix_for(path: Path, text: str) -> str:
    """Emit a re-ordered Dependencies table the agent can paste back."""
    rows = _extract_dependency_rows(text)
    if not rows:
        return ""
    # Group by step preserving step-group insertion order. Within each
    # group emit all read rows followed by all run rows, preserving the
    # original intra-kind order.
    groups: dict[str, list[tuple[int, str, str, str]]] = {}
    for entry in rows:
        groups.setdefault(entry[1], []).append(entry)
    lines = ["| Step | File | Kind |", "|------|------|------|"]
    for step, entries in groups.items():
        for entry in [e for e in entries if e[3] == "read"]:
            lines.append(f"| {entry[1]} | {entry[2]} | read |")
        for entry in [e for e in entries if e[3] == "run"]:
            lines.append(f"| {entry[1]} | {entry[2]} | run |")
    return "\n".join(lines)


def main() -> None:
    parser = cli.strict_parser(__doc__ or "")
    parser.add_argument("--path", type=Path, default=None)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--baseline", action="store_true")
    parser.add_argument(
        "--suggest-fix", action="store_true",
        help="Print the re-ordered Dependencies table for the supplied --path.",
    )
    # Peek at argv to decide whether to handle --suggest-fix locally
    # or delegate to the shared scaffold.
    args, _unknown = parser.parse_known_args()
    if args.suggest_fix:
        if not args.path or not args.path.is_file():
            output.error(
                "--suggest-fix requires an existing --path",
                hint="Pass --path $SKILLS/<skill>/SKILL.md",
            )
            return
        text = args.path.read_text(encoding="utf-8")
        suggested = _suggest_fix_for(args.path, text)
        output.success(
            {"file": str(args.path), "suggested_table": suggested},
            f"Suggested Dependencies-table ordering for {args.path}",
        )
        return

    run_skill_md_lint(
        rule_label="dependency-table ordering",
        lint_file=lint_file,
        script_name="internal_lints/skill_md_dependency_order.py",
    )


if __name__ == "__main__":
    cli.run_main(main)
