"""Author-time guardrails derived from the antipattern ruleset.

Emits one entry per error-severity rule so the ``pre-launch-check``
envelope can surface the write-time rule list to the agent before it
drafts ``requirements.md``. The YAML (`requirements_antipatterns.yaml`)
is the single source of truth for severity and rule ids — this module
only projects that data into the envelope shape.
"""
from __future__ import annotations

from typing import Iterable
from pathlib import Path

from ..deps import require_pyyaml

from .types import DATA_FILE

__all__ = ["Guardrail", "iter_error_rules", "load_raw_ruleset"]


class Guardrail(dict):
    """Envelope-shaped guardrail entry.

    Keys:
      - ``group``: canonical group name (e.g. ``path``).
      - ``rule``: rule id within the group (e.g. ``source-extension``).
      - ``severity``: effective severity (always ``error`` for this iterator).
      - ``summary``: one-line author-facing hint.
    """


# Short, author-oriented summaries per rule. Single source of truth for
# the text surfaced as ``authoring_guardrails[*].summary``; YAML owns
# severity + rule identity, this mapping owns the write-time phrasing.
_RULE_SUMMARIES: dict[tuple[str, str], str] = {
    ("path", "path-literal"): (
        "Do not use project-relative paths (src/, lib/); describe user behavior instead."
    ),
    ("path", "import-statement"): (
        "Imports belong in design.md / tasks.md — not requirements."
    ),
    ("path", "source-extension"): (
        "Do not reference source-file extensions (.py, .ts, .js, …); describe user behavior instead."
    ),
    ("structural", "headings-required"): (
        "Include the required H2 headings (Introduction, Requirements, Non-Functional Requirements)."
    ),
    ("structural", "user-story-present"): (
        "Include at least one 'As a [role], I want …, so that …' paragraph."
    ),
    ("structural", "acceptance-criterion-present"): (
        "Each requirement needs ≥1 WHEN/IF … THEN … SHALL acceptance criterion."
    ),
    ("structural", "no-empty-requirement-sections"): (
        "Every '## Requirement N' section must contain body content."
    ),
}


def load_raw_ruleset(path: Path | None = None) -> dict:
    """Return the parsed YAML ruleset without regex compilation.

    Thin read-only loader used by :func:`iter_error_rules` so callers
    never reach for the compiled ruleset just to inspect severity.
    """
    target = path or DATA_FILE
    yaml = require_pyyaml()
    with open(target, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def iter_error_rules(
    data: dict | None = None,
) -> Iterable[Guardrail]:
    """Yield :class:`Guardrail` for every error-severity rule.

    Covers both regex-based rules (listed under ``groups.<g>.rules``)
    and structural rules (listed under ``groups.structural.rule_ids``).
    Per-rule ``bug_fix_override`` entries never downgrade the write-
    time surface; the guardrail list reflects the canonical (standard-
    mode) severity so authors see every rule that might fire.
    """
    source = data or load_raw_ruleset()
    groups = source.get("groups") or {}
    for group_name, body in groups.items():
        if not isinstance(body, dict):
            continue
        severity = body.get("default_severity")
        if severity != "error":
            continue
        ids: list[str] = []
        for rule in body.get("rules") or []:
            if isinstance(rule, dict) and rule.get("id"):
                ids.append(str(rule["id"]))
        for rule_id in body.get("rule_ids") or []:
            if rule_id:
                ids.append(str(rule_id))
        seen: set[str] = set()
        for rule_id in ids:
            if rule_id in seen:
                continue
            seen.add(rule_id)
            summary = _RULE_SUMMARIES.get((group_name, rule_id))
            yield Guardrail(
                group=group_name,
                rule=rule_id,
                severity=severity,
                summary=summary or f"{group_name}/{rule_id}",
            )
