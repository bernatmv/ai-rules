#!/usr/bin/env python3
"""Lint SKILL.md / reference bodies for absolute ``.cursor`` / ``.claude``
skill paths.

Every cross-skill reference in a SKILL.md or reference file must use
the portable ``$SKILLS/<skill-name>/...`` prefix. An absolute path like
``/Users/.../.cursor/skills/...`` or ``/home/.../.claude/skills/...``
silently resolves today because the ``.claude/skills`` tree is a
symlink — but breaks on installs that ship without the opposite IDE's
mirror.

Usage:
  internal_lints/skill_md_abs_paths.py --path <SKILL.md>
  internal_lints/skill_md_abs_paths.py --all
  internal_lints/skill_md_abs_paths.py --baseline
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import re
from pathlib import Path

from sdd_core import cli, output, paths
from sdd_core.command_templates import build_shim_command
from sdd_core.paths import ide_skills_prefixes
from sdd_core.skill_md_rules import load_raw_rules
from sdd_core.text import iter_line_categories
from internal_lints._skill_md_lint_cli import collect_skill_targets

__sdd_manifest__ = {
    "summary": "SKILL.md absolute-path lint",
    "verbs": [
        "--path <skill.md>",
        "--all",
        "--baseline",
        "--scripts-scan",
    ],
    "flags": [
        "--path", "--all", "--baseline", "--scripts-scan", "--workspace",
    ],
}


def _build_abs_path_regex() -> re.Pattern[str]:
    """Assemble the absolute-path regex from :func:`ide_skills_prefixes`.

    Registering a new IDE skills tree becomes a single ``paths.py``
    edit — the lint picks it up on next import without touching this
    module.
    """
    leaves: list[str] = []
    for prefix in ide_skills_prefixes():
        head, _, tail = prefix.partition("/")
        if not tail:
            continue
        leaves.append(re.escape(head.lstrip(".")) + r"/" + re.escape(tail))
    leaf_alt = "|".join(leaves)
    return re.compile(
        r"(?:/Users/|/home/|/private/)(?:[^\s`'\"]*?/)?\.(?:" + leaf_alt + r")/"
    )


_ABS_PATH_RE = _build_abs_path_regex()
_SCRIPTS_ABS_PATH_RE = re.compile(
    r"\.(?:" + "|".join(
        re.escape(p.lstrip(".")) for p in ide_skills_prefixes()
    ) + r")/"
)


def _allowed(line: str, allow: list[str]) -> bool:
    return any(needle in line for needle in allow)


def lint_file(path: Path, rules: dict) -> list[dict]:
    """Return one violation dict per offending absolute-path line.

    Walks the file via :func:`sdd_core.text.iter_line_categories` so
    frontmatter / code-block categorisation stays in one place. Prose,
    markdown-fenced prose, and ``effective`` lines are all checked —
    only true ``frontmatter`` / non-markdown code fences are skipped.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    cfg = (rules or {}).get("absolute_skill_paths") or {}
    allow = list(cfg.get("allow", []))
    violations: list[dict] = []
    for i, raw, _stripped, category in iter_line_categories(text):
        if category == "frontmatter":
            continue
        if _ABS_PATH_RE.search(raw) and not _allowed(raw, allow):
            violations.append({
                "file": str(path),
                "line": i + 1,
                "message": (
                    "Absolute .cursor/.claude skill path; use "
                    "$SKILLS/<skill-name>/... instead."
                ),
                "snippet": raw.strip(),
            })
    return violations


def _targets(args, skills_root: Path) -> list[Path]:
    if args.path:
        return [args.path]
    return collect_skill_targets(skills_root, include_references=True)


def _scripts_targets(skills_root: Path) -> list[Path]:
    """Pipeline-phase Python files that compose sub-agent prompts.

    Extends the V.1 lint scope: the same ``.cursor/skills/…`` literal
    the SKILL.md bodies must never ship also has no business in the
    script that assembles the prompt path. Matches the prompt-assembly
    call graph (``commands.py`` → ``prompt_builder.py``) plus any
    future peer in ``pipeline_phases/``.
    """
    pipeline_dir = (
        skills_root / "sdd-common" / "scripts" / "review" / "pipeline_phases"
    )
    if not pipeline_dir.is_dir():
        return []
    return sorted(pipeline_dir.rglob("*.py"))


def lint_script_file(path: Path) -> list[dict]:
    """Return violations for ``.cursor/skills/...`` literals in Python.

    Skips strings prefixed by ``$SKILLS/`` (the canonical portable
    form) and comments that explicitly reference the banned pattern as
    a quoted counter-example.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    violations: list[dict] = []
    for i, raw in enumerate(text.splitlines()):
        if not _SCRIPTS_ABS_PATH_RE.search(raw):
            continue
        # ``$SKILLS/`` is the explicit allow form; bare ``$SKILLS`` is
        # the prefix constant, so allow any line that pairs the two.
        if "$SKILLS" in raw:
            continue
        violations.append({
            "file": str(path),
            "line": i + 1,
            "message": (
                "Literal .cursor/.claude skill path in Python; route "
                "through resolve_skills_prefix('$SKILLS/...') instead."
            ),
            "snippet": raw.strip(),
        })
    return violations


def main() -> None:
    parser = cli.strict_parser(__doc__)
    parser.add_argument("--path", type=Path, default=None)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--baseline", action="store_true")
    parser.add_argument(
        "--scripts-scan", action="store_true",
        help="Also scan review/pipeline_phases/*.py for .cursor/.claude literals.",
    )
    args = parser.parse_args()

    skills_root = Path(paths.find_skills_root())
    rules = load_raw_rules()
    targets = _targets(args, skills_root)

    all_violations: list[dict] = []
    for path in targets:
        all_violations.extend(lint_file(path, rules))
    if args.scripts_scan or args.all or args.baseline:
        for script_path in _scripts_targets(skills_root):
            all_violations.extend(lint_script_file(script_path))

    if args.baseline:
        output.success(
            {"violations": all_violations, "count": len(all_violations)},
            f"{len(all_violations)} absolute-path violations",
        )
        return

    if all_violations:
        output.error(
            f"{len(all_violations)} SKILL.md absolute-path violation(s)",
            hint="\n".join(
                f"{v['file']}:{v['line']} — {v['snippet']}"
                for v in all_violations
            ),
            next_action_command=build_shim_command(
                "internal_lints/skill_md_abs_paths.py", baseline=True,
            ),
        )
        return

    output.success(
        {"checked": [str(p) for p in targets]},
        f"{len(targets)} file(s) pass absolute-path lint",
    )


if __name__ == "__main__":
    cli.run_main(main)
