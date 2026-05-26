"""Shared CLI plumbing for every SKILL.md lint.

Owns argparse, ``--baseline``/``--path``/``--all`` semantics, target
discovery (glob ``*/SKILL.md`` under the skills root, skipping
``user-invocable: false``), and the ``output.success`` /
``output.error`` envelope. Per-lint modules declare only the rule
label, the per-file predicate, and (optionally) an
``include_references`` flag that widens the target walk to
``sdd-common/references/*.md``.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

from sdd_core import cli, output, paths
from sdd_core.command_templates import build_shim_command
from sdd_core.skill_md_rules import load_raw_rules

__all__ = [
    "run_skill_md_lint",
    "collect_skill_targets",
    "make_literal_lint",
]


LintFn = Callable[[Path, dict], list[dict]]


def _invocable_skill_dirs(skills_root: Path) -> list[Path]:
    """Return every ``<skills_root>/<skill>`` dir whose SKILL.md is user-invocable.

    Centralises the ``user-invocable: false`` skip rule so both the
    SKILL.md walk and the references walk inherit identical behaviour
    and any future change to the marker lands in one spot.
    """
    dirs: list[Path] = []
    for skill_md in sorted(skills_root.glob("*/SKILL.md")):
        try:
            text = skill_md.read_text(encoding="utf-8")
        except OSError:
            continue
        if "user-invocable: false" in text:
            continue
        dirs.append(skill_md.parent)
    return dirs


def collect_skill_targets(
    skills_root: Path, *, include_references: bool = False,
) -> list[Path]:
    """Return every user-invocable SKILL.md under *skills_root*.

    When *include_references* is ``True`` the walk also enumerates both
    the shared reference corpus (``sdd-common/references/*.md``) **and**
    each user-invocable skill's own ``references/*.md`` folder so every
    full-corpus lint reuses the same gathering logic.
    """
    skill_dirs = _invocable_skill_dirs(skills_root)
    results: list[Path] = [d / "SKILL.md" for d in skill_dirs]
    if not include_references:
        return results

    results.extend(sorted(
        (skills_root / "sdd-common" / "references").glob("*.md")
    ))
    for skill_dir in skill_dirs:
        if skill_dir.name == "sdd-common":
            continue
        ref_dir = skill_dir / "references"
        if ref_dir.is_dir():
            results.extend(sorted(ref_dir.glob("*.md")))
    return results


def run_skill_md_lint(
    *,
    rule_label: str,
    lint_file: LintFn,
    include_references: bool = False,
    script_name: str,
    error_summary: Callable[[int], str] | None = None,
) -> None:
    """Run a SKILL.md lint with the shared envelope / target walk.

    Parameters
    ----------
    rule_label:
        Human-readable label used in the success / baseline messages
        (e.g. ``"absolute-path"`` or ``"TOC-completeness"``).
    lint_file:
        Per-file predicate ``(path, rules) -> list[violation_dict]``.
    include_references:
        Forwarded to :func:`collect_skill_targets`.
    script_name:
        Relative shim path advertised in ``next_action_command`` (e.g.
        ``"internal_lints/skill_md_abs_paths.py"``).
    error_summary:
        Optional overrider for the error headline. Defaults to
        ``f"{n} SKILL.md {rule_label} violation(s)"``.
    """
    parser = cli.strict_parser(f"SKILL.md {rule_label} lint")
    parser.add_argument("--path", type=Path, default=None)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--baseline", "--refresh", action="store_true", dest="baseline")
    args = parser.parse_args()

    skills_root = Path(paths.find_skills_root())
    rules = load_raw_rules()

    if args.path:
        targets = [args.path]
    else:
        targets = collect_skill_targets(
            skills_root, include_references=include_references,
        )

    violations: list[dict] = []
    for path in targets:
        violations.extend(lint_file(path, rules))

    if args.baseline:
        output.success(
            {"violations": violations, "count": len(violations)},
            f"{len(violations)} {rule_label} violations",
        )
        return

    if violations:
        headline = (
            error_summary(len(violations))
            if error_summary is not None
            else f"{len(violations)} SKILL.md {rule_label} violation(s)"
        )
        output.error(
            headline,
            hint="\n".join(
                f"{v['file']}:{v.get('line', '?')} — "
                f"{v.get('message') or v.get('snippet', '')}"
                for v in violations
            ),
            next_action_command=build_shim_command(script_name, baseline=True),
        )
        return

    output.success(
        {"checked": [str(p) for p in targets]},
        f"{len(targets)} file(s) pass {rule_label} lint",
    )


def make_literal_lint(
    *,
    rule_key: str,
    default_regex: str,
    fallback_regex: "re.Pattern[str]",
    remediation_key: str,
    default_remediation: str,
    violation_kind: str,
    message_template: str,
) -> LintFn:
    """Return a ``lint_file`` predicate for the common regex-literal rule shape.

    Every rule whose shape is "forbidden regex + one-line remediation"
    delegates to this factory; the per-rule module declares only the
    four strings plus the message template. ``message_template`` is
    ``str.format``-evaluated with ``match=`` (``re.Match.group(0)``) and
    ``remediation=`` (the resolved remediation string) keyword args.
    """

    def _lint_file(path: Path, rules: dict) -> list[dict]:
        cfg = (rules or {}).get(rule_key) or {}
        if not cfg:
            return []
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return []
        pattern_src = cfg.get("forbidden_regex") or default_regex
        try:
            pattern = re.compile(pattern_src)
        except re.error:
            pattern = fallback_regex
        remediation = (
            cfg.get(remediation_key) or default_remediation
        ).strip()
        violations: list[dict] = []
        for idx, raw in enumerate(text.splitlines()):
            match = pattern.search(raw)
            if not match:
                continue
            violations.append({
                "file": str(path),
                "line": idx + 1,
                "kind": violation_kind,
                "snippet": raw.strip(),
                "message": message_template.format(
                    match=match.group(0), remediation=remediation,
                ),
            })
        return violations

    return _lint_file
