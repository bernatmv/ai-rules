"""Loader for ``data/skill_md_rules.yaml``.

The data file is the single source of truth for SKILL.md compliance
checks (forbidden literals, per-skill positive rules, line budget,
freedom-column requirement). Adding a new rule is a YAML edit only;
this loader keeps the schema-thin Python layer.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .deps import require_pyyaml

__all__ = [
    "DATA_FILE",
    "ForbiddenLiteral",
    "RequiredLiteral",
    "SkillRules",
    "RulesBundle",
    "load_rules",
    "load_raw_rules",
    "dependencies_for_skill",
    "rules_for_skill",
]


DATA_FILE = Path(__file__).resolve().parent / "data" / "skill_md_rules.yaml"
_BACKTICK_PATH_RE = re.compile(r"`([^`]+)`")


@dataclass(frozen=True)
class ForbiddenLiteral:
    literal: str
    remediation: str


@dataclass(frozen=True)
class RequiredLiteral:
    literal: str
    remediation: str


@dataclass(frozen=True)
class SkillRules:
    """Per-skill rule bundle.

    ``max_lines`` of ``0`` (the default) disables the budget check.
    ``require_freedom_column`` defaults to ``False`` so adding a new
    skill is opt-in.
    """

    name: str
    max_lines: int = 0
    require_freedom_column: bool = False
    required_literals: tuple[RequiredLiteral, ...] = ()


@dataclass(frozen=True)
class RulesBundle:
    forbidden: tuple[ForbiddenLiteral, ...]
    per_skill: dict[str, SkillRules] = field(default_factory=dict)


_CACHE: RulesBundle | None = None


def _coerce_forbidden(items: Any) -> tuple[ForbiddenLiteral, ...]:
    out: list[ForbiddenLiteral] = []
    if isinstance(items, list):
        for entry in items:
            if not isinstance(entry, dict):
                continue
            literal = entry.get("literal")
            if not isinstance(literal, str):
                continue
            out.append(ForbiddenLiteral(
                literal=literal,
                remediation=str(entry.get("remediation", "")).strip(),
            ))
    return tuple(out)


def _coerce_required(items: Any) -> tuple[RequiredLiteral, ...]:
    out: list[RequiredLiteral] = []
    if isinstance(items, list):
        for entry in items:
            if not isinstance(entry, dict):
                continue
            literal = entry.get("literal")
            if not isinstance(literal, str):
                continue
            out.append(RequiredLiteral(
                literal=literal,
                remediation=str(entry.get("remediation", "")).strip(),
            ))
    return tuple(out)


def _coerce_skill(name: str, raw: Any) -> SkillRules:
    if not isinstance(raw, dict):
        return SkillRules(name=name)
    return SkillRules(
        name=name,
        max_lines=int(raw.get("max_lines") or 0),
        require_freedom_column=bool(raw.get("require_freedom_column", False)),
        required_literals=_coerce_required(raw.get("required_literals")),
    )


def load_rules(*, refresh: bool = False) -> RulesBundle:
    """Load (and cache) the YAML rules bundle.

    Pass ``refresh=True`` from tests that mutate the data file.
    """
    global _CACHE
    if _CACHE is not None and not refresh:
        return _CACHE
    yaml = require_pyyaml()
    with open(DATA_FILE, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    forbidden = _coerce_forbidden(raw.get("forbidden"))
    per_skill: dict[str, SkillRules] = {}
    raw_per_skill = raw.get("per_skill") or {}
    if isinstance(raw_per_skill, dict):
        for name, payload in raw_per_skill.items():
            per_skill[str(name)] = _coerce_skill(str(name), payload)
    _CACHE = RulesBundle(forbidden=forbidden, per_skill=per_skill)
    return _CACHE


def load_raw_rules() -> dict:
    """Return the YAML bundle as a raw dict.

    Exists for lints whose rule shape doesn't map cleanly onto the
    structured :class:`RulesBundle` (e.g. ``prompt_invocation_adjacency``
    with nested lists of templates).
    """
    yaml = require_pyyaml()
    with open(DATA_FILE, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def rules_for_skill(skill_name: str) -> SkillRules:
    """Return rules for *skill_name* (or an empty :class:`SkillRules`)."""
    bundle = load_rules()
    return bundle.per_skill.get(skill_name, SkillRules(name=skill_name))


def dependencies_for_skill(
    skill_name: str, *, project_path: str = "",
) -> dict[str, str]:
    """Return ``absolute dependency path -> freedom`` from a SKILL table.

    Three-column legacy tables default to ``L`` so rollout stays
    conservative until every user-invocable SKILL declares the column.
    """
    from sdd_core.skill_links_resolve import resolve_skills_prefix

    skill_md = resolve_skills_prefix(
        f"$SKILLS/{skill_name}/SKILL.md", project_path=project_path,
    )
    try:
        text = Path(skill_md).read_text(encoding="utf-8")
    except OSError:
        return {}
    rows: dict[str, str] = {}
    in_table = False
    headers: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("|"):
            if in_table:
                break
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        normalised = [cell.lower() for cell in cells]
        if "step" in normalised and "file" in normalised and "kind" in normalised:
            in_table = True
            headers = normalised
            continue
        if not in_table or set(line.replace("|", "").replace(":", "").strip()) <= {"-"}:
            continue
        if len(cells) < 3:
            continue
        file_idx = headers.index("file") if "file" in headers else 1
        kind_idx = headers.index("kind") if "kind" in headers else 2
        freedom_idx = headers.index("freedom") if "freedom" in headers else -1
        kind = cells[kind_idx].lower() if kind_idx < len(cells) else ""
        if kind != "read":
            continue
        match = _BACKTICK_PATH_RE.search(cells[file_idx] if file_idx < len(cells) else "")
        if not match:
            continue
        path = resolve_skills_prefix(match.group(1), project_path=project_path)
        freedom = "L"
        if freedom_idx >= 0 and freedom_idx < len(cells):
            candidate = cells[freedom_idx].strip().upper()
            if candidate in {"L", "M", "H"}:
                freedom = candidate
        rows[os.path.abspath(path)] = freedom
    return rows


def skill_name_from_md_path(md_path: str) -> str | None:
    """Infer the skill name from a SKILL.md path (parent directory)."""
    normalised = os.path.normpath(md_path)
    if not normalised.endswith(os.sep + "SKILL.md") and not normalised.endswith("/SKILL.md"):
        return None
    return os.path.basename(os.path.dirname(normalised)) or None
