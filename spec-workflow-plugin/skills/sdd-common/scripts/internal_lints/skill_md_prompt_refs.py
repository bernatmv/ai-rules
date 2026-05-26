#!/usr/bin/env python3
"""Lint SKILL.md files for adjacent prompt-invocation commands.

Every mention of a prompt ID (from prompt-registry.json) inside a
user-invocable SKILL.md body must be followed — within a configurable
line window — by a fenced code block carrying the exact shim command:

    .spec-workflow/sdd util/generate-prompt.py --type <prompt-id> ...

The rule set is data-driven (sdd_core/data/skill_md_rules.yaml §
prompt_invocation_adjacency); this lint is the enforcement arm.

Usage:
  internal_lints/skill_md_prompt_refs.py --path <SKILL.md>
  internal_lints/skill_md_prompt_refs.py --all
  internal_lints/skill_md_prompt_refs.py --baseline
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import re
from pathlib import Path

from sdd_core import cli, output, paths
from sdd_core.prompts import load_registry
from sdd_core.skill_md_rules import load_raw_rules
from sdd_core.text import iter_line_categories

__sdd_manifest__ = {
    "summary": "SKILL.md prompt-invocation adjacency lint",
    "verbs": [
        "--path <skill.md>",
        "--all",
        "--baseline",
    ],
    "flags": ["--path", "--all", "--baseline", "--workspace"],
}


def _skill_md_paths(skills_root: Path) -> list[Path]:
    """Return every user-invocable SKILL.md under the skills root."""
    results: list[Path] = []
    for p in sorted(skills_root.glob("*/SKILL.md")):
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        if "user-invocable: false" in text:
            continue
        results.append(p)
    return results


def registry_prompt_ids() -> set[str]:
    """Return every prompt-id declared in the registry."""
    return set((load_registry().get("prompts") or {}).keys())


def _fenced_ranges(content: str) -> list[tuple[int, int]]:
    """Return ``(start_line_idx, end_line_idx)`` pairs (inclusive) per block.

    Uses :func:`sdd_core.text.iter_line_categories` so fence detection
    stays in one place. Each range spans the opening and closing fence
    lines.
    """
    ranges: list[tuple[int, int]] = []
    start: int | None = None
    last: int = 0
    for i, _raw, _stripped, cat in iter_line_categories(content):
        if cat == "code_block":
            if start is None:
                start = i
            last = i
        elif start is not None:
            ranges.append((start, last))
            start = None
    if start is not None:
        ranges.append((start, last))
    return ranges


def _mentions(
    lines: list[str], prompt_id: str, ranges: list[tuple[int, int]],
) -> list[int]:
    """Return line indices mentioning ``prompt_id`` outside fenced blocks."""

    def _in_block(i: int) -> bool:
        return any(s < i < e for s, e in ranges)

    pattern = re.compile(rf"`{re.escape(prompt_id)}`")
    return [
        i for i, line in enumerate(lines)
        if pattern.search(line) and not _in_block(i)
    ]


def _has_adjacent_command(
    lines: list[str], mention_line: int, prompt_id: str,
    ranges: list[tuple[int, int]],
    *, max_distance: int, accepted: list[str],
) -> bool:
    for start, end in ranges:
        if start <= mention_line:
            continue
        if start - mention_line > max_distance:
            continue
        body = "\n".join(lines[start + 1:end])
        for template in accepted:
            needle = template.format(prompt_id=prompt_id)
            if needle in body:
                return True
    return False


def lint_file(path: Path, rules: dict, prompt_ids: set[str]) -> list[dict]:
    """Return one violation dict per unpaired prompt mention."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    lines = text.splitlines()
    ranges = _fenced_ranges(text)
    cfg = (rules or {}).get("prompt_invocation_adjacency") or {}
    max_dist = int(cfg.get("max_distance_lines", 20))
    accepted = list(cfg.get("accepted_commands", []))
    ignore_phrases = list(cfg.get("ignore_phrases", []))
    msg_template = cfg.get("violation_message", "")
    violations: list[dict] = []
    for pid in sorted(prompt_ids):
        if pid in ignore_phrases:
            continue
        for line_idx in _mentions(lines, pid, ranges):
            if any(ph in lines[line_idx] for ph in ignore_phrases):
                continue
            if _has_adjacent_command(
                lines, line_idx, pid, ranges,
                max_distance=max_dist, accepted=accepted,
            ):
                continue
            violations.append({
                "file": str(path),
                "line": line_idx + 1,
                "prompt_id": pid,
                "message": msg_template.format(
                    prompt_id=pid, max_distance_lines=max_dist,
                ),
            })
    return violations


def main() -> None:
    parser = cli.strict_parser(__doc__)
    parser.add_argument("--path", type=Path, default=None)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--baseline", "--refresh", action="store_true", dest="baseline")
    args = parser.parse_args()

    skills_root = Path(paths.find_skills_root())
    rules = load_raw_rules()
    prompt_ids = registry_prompt_ids()

    if args.path:
        targets = [args.path]
    elif args.all or args.baseline:
        targets = _skill_md_paths(skills_root)
    else:
        output.error(
            "Provide --path <SKILL.md> or --all",
            hint="Baseline sweep: --baseline",
            next_action_command=(
                "internal_lints/skill_md_prompt_refs.py --all"
            ),
        )
        return

    all_violations: list[dict] = []
    for path in targets:
        all_violations.extend(lint_file(path, rules, prompt_ids))

    if args.baseline:
        output.success(
            {"violations": all_violations, "count": len(all_violations)},
            f"{len(all_violations)} prompt-invocation violations",
        )
        return

    if all_violations:
        output.error(
            f"{len(all_violations)} SKILL.md prompt-invocation violation(s)",
            hint="\n".join(
                f"{v['file']}:{v['line']} — {v['message']}"
                for v in all_violations
            ),
            next_action_command=(
                "internal_lints/skill_md_prompt_refs.py --baseline"
            ),
        )
        return

    output.success(
        {"checked": [str(p) for p in targets]},
        f"{len(targets)} SKILL.md file(s) pass prompt-invocation adjacency",
    )


if __name__ == "__main__":
    cli.run_main(main)
