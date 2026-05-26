"""Loader for ``data/facet_promotion_rules.yaml``.

Companion to ``review_quality.promotion`` — that module applies the
loaded rules to a facet's ``cited_issues_history``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .data_loader import load_yaml

__all__ = [
    "DATA_FILENAME",
    "PromotionRule",
    "load_rules",
]


DATA_FILENAME = "facet_promotion_rules.yaml"


@dataclass(frozen=True)
class PromotionRule:
    name: str
    match_kind: str
    preconditions: dict
    consequence: dict


_CACHE: "dict[str, PromotionRule] | None" = None


def _coerce_rule(name: str, raw: Any) -> PromotionRule:
    if not isinstance(raw, dict):
        return PromotionRule(name=name, match_kind="", preconditions={}, consequence={})
    pre = raw.get("preconditions") or {}
    con = raw.get("consequence") or {}
    return PromotionRule(
        name=name,
        match_kind=str(raw.get("match_kind") or ""),
        preconditions=pre if isinstance(pre, dict) else {},
        consequence=con if isinstance(con, dict) else {},
    )


def load_rules(*, refresh: bool = False) -> dict[str, PromotionRule]:
    """Return ``{rule_name: PromotionRule}``."""
    global _CACHE
    if _CACHE is not None and not refresh:
        return _CACHE
    raw = load_yaml(DATA_FILENAME) or {}
    rules_raw = raw.get("rules") or {}
    rules: dict[str, PromotionRule] = {}
    if isinstance(rules_raw, dict):
        for name, payload in rules_raw.items():
            rules[str(name)] = _coerce_rule(str(name), payload)
    _CACHE = rules
    return _CACHE
