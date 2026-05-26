#!/usr/bin/env python3
"""Lint: every owned skill's ``references/handoffs.md`` mirrors the registry.

Each user-invocable SKILL.md owns a handoff table in
``references/handoffs.md``; SKILL.md itself carries a 3-line stub
pointing at the reference. The lint cross-checks: for every
script id whose vertical maps to a registered skill, the
``references/handoffs.md`` body must contain the literal ``command``
from the registry — drift between the two is a hard error.

Skill ownership is data-driven via :data:`_SKILL_OWNERSHIP`. Adding a
new skill / script-id family takes one row.

Usage:
  .spec-workflow/sdd internal_lints/skill_md_handoff_table.py
      — diff each ``references/handoffs.md`` against the registry.
  .spec-workflow/sdd internal_lints/skill_md_handoff_table.py --refresh
      — rewrite the baseline.
  .spec-workflow/sdd internal_lints/skill_md_handoff_table.py --rewrite
      — regenerate ``references/handoffs.md`` from the registry.
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

from pathlib import Path
from typing import Iterable

from internal_lints import LintFinding
from internal_lints._dispatch import rule_id_for
from internal_lints.base import LintSpec, run_lint
from sdd_core import cli, handoffs, output, paths

_RULE_ID = rule_id_for(__name__, __file__)

# Skill → script-id prefix. Each user-invocable SKILL.md owns the
# handoff rows whose ``script_id`` starts with the prefix. Adding a
# skill is a one-line change; adding a new prefix means a new vertical.
_SKILL_OWNERSHIP: dict[str, tuple[str, ...]] = {
    "sdd-workspace-create-spec": ("workspace/",),
    "sdd-create-spec": ("spec/",),
    "sdd-create-discovery": ("discovery/",),
    "sdd-create-prd": ("prd/",),
}

_SECTION_HEADING = "## Handoffs"
_HANDOFFS_REFERENCE_REL = "references/handoffs.md"
_REGEN_SHIM = (
    ".spec-workflow/sdd internal_lints/skill_md_handoff_table.py --rewrite"
)
_SKILL_STUB_BODY = (
    f"\nSee `{_HANDOFFS_REFERENCE_REL}` (generated from "
    "`$SCRIPTS/handoff-registry.json`).\n"
    f"Regenerate via `{_REGEN_SHIM}`.\n"
)


def _ownership_root() -> Path:
    """Return the workspace skills root containing every SKILL.md."""
    return Path(paths.find_skills_root())


def target_path_for_skill(skill_name: str) -> Path:
    """Return the absolute ``references/handoffs.md`` path for *skill_name*."""
    return _ownership_root() / skill_name / _HANDOFFS_REFERENCE_REL


def _resolve_handoff_command(ho: dict) -> str:
    """Return the literal command for a registry handoff row.

    Emitter-form rows (``ho["emitter"]`` populated) dispatch to
    ``sdd_core.command_templates.<emitter>`` with the kwargs taken
    verbatim — ``{ctx.X}`` placeholders pass through to the literal
    so the rendered handoff line stays generic and the operator
    sees the same placeholder shape they will substitute at runtime.
    Static rows return the literal ``command`` field unchanged.

    A row that declares both ``emitter`` and ``command`` prefers the
    emitter render; the static field is the legacy fallback when the
    emitter cannot be resolved.
    """
    emitter_name = str(ho.get("emitter") or "")
    if emitter_name:
        kwargs_template = ho.get("kwargs") or {}
        if isinstance(kwargs_template, dict):
            try:
                from sdd_core import command_templates as _ct
                emitter = getattr(_ct, emitter_name, None)
                if callable(emitter):
                    bound = {
                        str(k): str(v)
                        for k, v in kwargs_template.items()
                        if isinstance(v, str) and v
                    }
                    return str(emitter(**bound))
            except (ImportError, TypeError, ValueError, KeyError):
                # Fall through to the static command on any emitter
                # resolution failure so the handoff stub still renders.
                pass
    return str(ho.get("command") or "").strip()


def _registry_handoffs_for(prefix_set: tuple[str, ...]) -> list[tuple[str, dict]]:
    """Return ``(script_id, handoff)`` pairs for ids matching any prefix.

    Each handoff dict carries a ``_rendered_command`` key the renderer
    consumes — emitter-form rows resolve via ``command_templates`` so
    drift between the static stub and the canonical builder cannot
    survive a regen.
    """
    registry = handoffs.load_registry()
    scripts = registry.get("scripts") or {}
    matched: list[tuple[str, dict]] = []
    for script_id, entry in sorted(scripts.items()):
        if not any(script_id.startswith(p) for p in prefix_set):
            continue
        for ho in entry.get("handoffs") or []:
            command = _resolve_handoff_command(ho)
            if not command:
                continue
            ho_with_command = dict(ho)
            ho_with_command["command"] = command
            matched.append((script_id, ho_with_command))
    return matched


def _extract_section(text: str, heading: str) -> "str | None":
    """Return the body text under ``heading`` (up to the next H2)."""
    lines = text.splitlines()
    start: int | None = None
    for i, line in enumerate(lines):
        if line.strip() == heading:
            start = i + 1
            break
    if start is None:
        return None
    end = len(lines)
    for j in range(start, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break
    return "\n".join(lines[start:end])


def _render_section(rows: list[tuple[str, dict]]) -> str:
    """Render the table body as a compact markdown table (no heading)."""
    out: list[str] = [
        "| Script | Handoff | Command | Note |",
        "|--------|---------|---------|------|",
    ]
    for script_id, ho in rows:
        note = (ho.get("note") or "").strip().replace("|", "\\|")
        command = ho["command"].replace("|", "\\|")
        out.append(
            f"| `{script_id}` | `{ho['id']}` | `{command}` | {note} |"
        )
    return "\n".join(out)


def render_handoff_section_for_skill(skill_name: str) -> "str | None":
    """Return the rendered ``references/handoffs.md`` body for *skill_name*.

    Returns ``None`` when the skill has no registered handoffs.
    """
    prefixes = _SKILL_OWNERSHIP.get(skill_name)
    if prefixes is None:
        return None
    rows = _registry_handoffs_for(prefixes)
    if not rows:
        return None
    header = (
        f"# {skill_name} — Handoffs\n"
        "\n"
        "Generated from `$SCRIPTS/handoff-registry.json`. Do not hand-edit;\n"
        f"run `{_REGEN_SHIM}` to regenerate.\n"
        "\n"
    )
    return header + _render_section(rows) + "\n"


class _HandoffTableChecker:
    """Per-file checker — fires once per SKILL.md path under a known skill.

    Validates two surfaces:
      * ``SKILL.md`` carries the 3-line stub pointing at
        ``references/handoffs.md``.
      * ``references/handoffs.md`` contains every registered handoff
        ``command`` for the owning vertical.
    """

    rule_id = _RULE_ID
    severity = "error"

    def check_path(self, path: Path) -> Iterable[LintFinding]:
        if path.name != "SKILL.md":
            return ()
        skill_dir = path.parent.name
        prefixes = _SKILL_OWNERSHIP.get(skill_dir)
        if prefixes is None:
            return ()
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return ()
        if "user-invocable: false" in text:
            return ()
        rows = _registry_handoffs_for(prefixes)
        findings: list[LintFinding] = []
        section = _extract_section(text, _SECTION_HEADING)
        if section is None:
            findings.append(LintFinding(
                rule_id=self.rule_id,
                severity=self.severity,
                file=str(path),
                line=1,
                message=(
                    f"SKILL.md is missing the `## Handoffs` stub. Run "
                    f"`{_REGEN_SHIM}` to install the reference pointer."
                ),
            ))
            return findings
        if _HANDOFFS_REFERENCE_REL not in section:
            findings.append(LintFinding(
                rule_id=self.rule_id,
                severity=self.severity,
                file=str(path),
                line=1,
                message=(
                    f"`## Handoffs` should point at "
                    f"`{_HANDOFFS_REFERENCE_REL}`. Run `{_REGEN_SHIM}`."
                ),
            ))
        ref_path = path.parent / _HANDOFFS_REFERENCE_REL
        ref_text = ""
        if ref_path.is_file():
            try:
                ref_text = ref_path.read_text(encoding="utf-8")
            except OSError:
                ref_text = ""
        if not ref_text and rows:
            findings.append(LintFinding(
                rule_id=self.rule_id,
                severity=self.severity,
                file=str(ref_path),
                line=1,
                message=(
                    f"`{_HANDOFFS_REFERENCE_REL}` is missing or empty. "
                    f"Run `{_REGEN_SHIM}` to generate from the registry."
                ),
            ))
            return findings
        for script_id, ho in rows:
            if ho["command"] not in ref_text:
                findings.append(LintFinding(
                    rule_id=self.rule_id,
                    severity=self.severity,
                    file=str(ref_path),
                    line=1,
                    message=(
                        f"`{_HANDOFFS_REFERENCE_REL}` is missing or stale "
                        f"for {script_id} → {ho['id']!r}. Run "
                        f"`{_REGEN_SHIM}`."
                    ),
                ))
        return findings


def _replace_section(text: str, heading: str, body: str) -> str:
    """Insert or replace ``heading`` body inside *text*; return new text."""
    lines = text.splitlines()
    start: int | None = None
    for i, line in enumerate(lines):
        if line.strip() == heading:
            start = i
            break
    new_block = [heading, body.rstrip(), ""]
    if start is None:
        # Append a fresh section to the end of the file.
        trailing = "" if text.endswith("\n") else "\n"
        return text + trailing + "\n" + "\n".join(new_block)
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break
    new_lines = lines[:start] + new_block + lines[end:]
    return "\n".join(new_lines).rstrip() + "\n"


def _rewrite_all() -> None:
    """Write ``references/handoffs.md`` for every owned skill, install SKILL.md stub."""
    skills_root = _ownership_root()
    rewrites: list[str] = []
    for skill, _prefixes in _SKILL_OWNERSHIP.items():
        skill_md = skills_root / skill / "SKILL.md"
        if not skill_md.is_file():
            continue
        body = render_handoff_section_for_skill(skill)
        if body is None:
            continue
        ref_path = target_path_for_skill(skill)
        ref_path.parent.mkdir(parents=True, exist_ok=True)
        if not ref_path.is_file() or ref_path.read_text(encoding="utf-8") != body:
            ref_path.write_text(body, encoding="utf-8")
            rewrites.append(str(ref_path))
        text = skill_md.read_text(encoding="utf-8")
        new_text = _replace_section(text, _SECTION_HEADING, _SKILL_STUB_BODY)
        if new_text != text:
            skill_md.write_text(new_text, encoding="utf-8")
            rewrites.append(str(skill_md))
    output.success(
        {"rewritten": rewrites, "count": len(rewrites)},
        f"Regenerated handoff surface in {len(rewrites)} file(s)",
    )


SPEC = LintSpec(
    rule_id=_RULE_ID,
    roots=(".cursor/skills",),
    path_checkers=(_HandoffTableChecker(),),
    file_glob="SKILL.md",
)


analyze = SPEC.analyze
compare_baseline = SPEC.compare_baseline


def main() -> None:
    parser = cli.strict_parser(__doc__ or "")
    parser.add_argument(
        "--refresh", action="store_true",
        help="Rewrite the baseline to match observed findings.",
    )
    parser.add_argument(
        "--rewrite", action="store_true",
        help=(
            "Regenerate `## Handoffs` sections in every owned SKILL.md "
            "from the registry. Use after registry changes."
        ),
    )
    args = parser.parse_args()
    if args.rewrite:
        _rewrite_all()
        return
    run_lint(SPEC, refresh=args.refresh)


if __name__ == "__main__":
    cli.run_main(main)
