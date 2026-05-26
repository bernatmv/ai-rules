#!/usr/bin/env python3
"""Lint SKILL.md files for hand-rendered lettered option lists.

Every time a SKILL.md references a ``generate-prompt.py --type <id>``
command it MUST NOT also ship a hand-written ``- (a) …`` / ``- (b) …``
bullet block within ``max_distance_lines`` (see
``skill_md_rules.yaml::hand_rendered_options``). Bullets inside a
fenced ``markdown`` block labelled as the auto-rendered output
example are accepted — the goal is to catch bullets in the agent's
own prose, not in documentation of the registry output.

Usage:
  internal_lints/skill_md_hand_rendered_options.py --path <SKILL.md>
  internal_lints/skill_md_hand_rendered_options.py --all
  internal_lints/skill_md_hand_rendered_options.py --baseline
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import re
from pathlib import Path

from sdd_core import cli
from sdd_core.text import iter_line_categories
from internal_lints._skill_md_lint_cli import run_skill_md_lint

__sdd_manifest__ = {
    "summary": "SKILL.md hand-rendered-options lint",
    "verbs": [
        "--path <skill.md>",
        "--all",
        "--baseline",
    ],
    "flags": ["--path", "--all", "--baseline", "--workspace"],
}


# ``- (a) Option`` / ``> - (a) Option`` / ``1. (a) Option``. The lead
# marker (``- ``, ``> - ``, digits) is the tell for a lettered option
# bullet; the parenthetical letter is what distinguishes the pattern
# from ordinary prose bullets.
_HAND_BULLET_RE = re.compile(r"^\s*>?\s*(?:[-*]|\d+\.)\s*\(([a-z])\)\s+", re.I)
_PROMPT_REF_RE = re.compile(
    r"generate-prompt\.py\s+--type\s+([A-Za-z0-9_\-]+)"
)


def _auto_render_block_ranges(text: str) -> list[tuple[int, int]]:
    r"""Return ``(start, end)`` line ranges for fenced ``markdown`` blocks
    that appear to show the auto-rendered prompt output.

    We match only blocks opened with ``\`\`\`markdown`` so ordinary
    ``\`\`\`\`` (language-less) examples still fail the lint — the
    language tag is the signal that the bullets are illustrative, not
    live.
    """
    ranges: list[tuple[int, int]] = []
    start: int | None = None
    opener_is_markdown = False
    for i, raw, _stripped, cat in iter_line_categories(text):
        if cat == "code_block":
            if start is None:
                start = i
                opener_is_markdown = "markdown" in raw.lower()
        elif start is not None:
            if opener_is_markdown:
                ranges.append((start, i - 1))
            start = None
            opener_is_markdown = False
    if start is not None and opener_is_markdown:
        ranges.append((start, len(text.splitlines()) - 1))
    return ranges


def _iter_prompt_mentions(lines: list[str]) -> list[tuple[int, str]]:
    results: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        match = _PROMPT_REF_RE.search(line)
        if match:
            results.append((i, match.group(1)))
    return results


def _iter_hand_bullets(lines: list[str]) -> list[int]:
    return [i for i, line in enumerate(lines) if _HAND_BULLET_RE.match(line)]


def lint_file(path: Path, rules: dict) -> list[dict]:
    """Return violations for hand-rendered options near a prompt reference.

    A violation fires when two or more consecutive lettered bullets
    appear within ``max_distance_lines`` of a ``generate-prompt.py
    --type <id>`` mention and are *not* inside a fenced ``markdown``
    block. Two bullets is the minimum — a single ``(a)`` may be a
    nested list marker, not a forged option menu.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    cfg = (rules or {}).get("hand_rendered_options") or {}
    max_dist = int(cfg.get("max_distance_lines", 20))

    lines = text.splitlines()
    prompt_mentions = _iter_prompt_mentions(lines)
    if not prompt_mentions:
        return []
    bullet_lines = _iter_hand_bullets(lines)
    if len(bullet_lines) < 2:
        return []
    allowed_ranges = _auto_render_block_ranges(text)

    def _in_allowed_block(idx: int) -> bool:
        return any(start <= idx <= end for start, end in allowed_ranges)

    violations: list[dict] = []
    for mention_line, prompt_id in prompt_mentions:
        nearby = [
            b for b in bullet_lines
            if abs(b - mention_line) <= max_dist and not _in_allowed_block(b)
        ]
        if len(nearby) < 2:
            continue
        nearby.sort()
        # Only flag consecutive bullets (adjacent line indices) so a
        # single stray ``(a)`` in prose doesn't pair up with unrelated
        # bullets elsewhere in the window.
        for i in range(len(nearby) - 1):
            if nearby[i + 1] - nearby[i] > 2:
                continue
            violations.append({
                "file": str(path),
                "line": nearby[i] + 1,
                "kind": "hand_rendered_options",
                "prompt_id": prompt_id,
                "message": (
                    f"Hand-rendered lettered options near "
                    f"`generate-prompt.py --type {prompt_id}`. "
                    "Render via the registry; fence the example with "
                    "```markdown if documenting the auto-rendered "
                    "output."
                ),
            })
            break
    return violations


def main() -> None:
    run_skill_md_lint(
        rule_label="hand-rendered-options",
        lint_file=lint_file,
        script_name="internal_lints/skill_md_hand_rendered_options.py",
    )


if __name__ == "__main__":
    cli.run_main(main)
