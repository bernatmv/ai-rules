"""YAML ruleset loading and compilation for the validator.

Keeps the YAML-facing plumbing (file read, regex compilation, matcher
construction) isolated from the finding-emission logic. The compiled
ruleset is a plain dict so tests can build tiny bespoke rulesets
without touching the YAML.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Iterable

from ..deps import require_pyyaml
from ..matchers import WordMatcher
from .types import DATA_FILE, STRATEGY_REGEX, STRATEGY_WORD

__all__ = [
    "DATA_FILE",
    "load_ruleset",
]

yaml = require_pyyaml()


def _maybe_strict_validate(data: dict[str, Any]) -> None:
    """Opt-in schema gate for local development.

    When ``SDD_STRICT_YAML=1`` is set, we run the test-support schema
    validator eagerly so a mistyped YAML key fails loudly with a
    targeted ``ValidationError`` instead of surfacing as a cryptic
    ``KeyError`` much later during ``validate_content``. The import
    is lazy-gated so dev-only tooling is never loaded in CI/runtime.
    """
    if os.environ.get("SDD_STRICT_YAML") != "1":
        return
    try:
        from tests._support.antipattern_data_validator import validate_data
    except Exception:  # pragma: no cover - dev-only tree may be absent
        return
    validate_data(data)


def _compile_group_rules(group_name: str, body: dict[str, Any]) -> list[dict[str, Any]]:
    """Compile per-rule regex patterns into ready-to-match objects."""
    compiled: list[dict[str, Any]] = []
    for rule in body.get("rules") or []:
        pattern = rule["pattern"]
        compiled.append({
            "group": group_name,
            "id": rule["id"],
            "regex": re.compile(pattern),
            "suggestion": rule.get("suggestion"),
            "bug_fix_override": rule.get("bug_fix_override"),
            # Optional literal-replacement template surfaced as
            # ``Finding.replacement_text``. Carries ``{match}`` (and
            # optionally ``{section}`` / ``{spec_name}``) — the line
            # dispatcher renders it against the matched literal.
            "replacement_template": rule.get("replacement_template"),
        })
    return compiled


def _build_word_matcher(
    words: Iterable[str],
    *,
    case_sensitive: bool,
) -> WordMatcher:
    return WordMatcher(list(words), case_sensitive=case_sensitive, boundary="word")


def load_ruleset(path: Path | None = None) -> dict[str, Any]:
    """Load and compile the antipattern YAML into a ready-to-run ruleset."""
    target = path or DATA_FILE
    with open(target, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    _maybe_strict_validate(data)

    groups: dict[str, Any] = {}
    for name, body in (data.get("groups") or {}).items():
        compiled_rules = _compile_group_rules(name, body)

        words = body.get("words")
        word_matcher = None
        if words:
            word_matcher = _build_word_matcher(
                words, case_sensitive=bool(body.get("case_sensitive", False)),
            )

        env_literals = body.get("env_var_literals") or {}
        env_matcher = None
        if env_literals.get("words"):
            env_matcher = _build_word_matcher(
                env_literals["words"],
                case_sensitive=bool(env_literals.get("case_sensitive", True)),
            )

        pkg_managers = body.get("package_managers") or {}
        pkg_matcher = None
        pkg_co_matcher = None
        if pkg_managers.get("words"):
            pkg_matcher = _build_word_matcher(
                pkg_managers["words"],
                case_sensitive=bool(pkg_managers.get("case_sensitive", False)),
            )
            co_words = pkg_managers.get("co_occurrence") or []
            if co_words:
                # Word-boundary matcher so "reinstalled" does not gate the
                # package rule via substring ``install``. Case-insensitive
                # to match operator intent across camelCase prose.
                pkg_co_matcher = _build_word_matcher(
                    co_words, case_sensitive=False,
                )

        # Derive dispatch strategy from declared data. Structural groups
        # (``rules == []`` and ``words is None``) fall through to the
        # coded-rule branch in ``line_findings.iter_line_findings``.
        if words:
            strategy = STRATEGY_WORD
        elif compiled_rules:
            strategy = STRATEGY_REGEX
        else:
            strategy = None

        groups[name] = {
            "default_severity": body.get("default_severity"),
            "bug_fix_override": body.get("bug_fix_override"),
            "section_aware": body.get("section_aware") or {},
            "rules": compiled_rules,
            "word_matcher": word_matcher,
            "env_matcher": env_matcher,
            "package_matcher": pkg_matcher,
            "package_co_matcher": pkg_co_matcher,
            "rule_ids": body.get("rule_ids") or [],
            "match_strategy": strategy,
            # Per-group user-facing copy. YAML owns the template so a new
            # canonical group ships entirely from the data side.
            "message_template": body.get("message_template"),
        }
    return {"groups": groups}
