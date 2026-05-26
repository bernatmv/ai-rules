"""Tier 2 facet score promotion.

Reads ``cited_issues_history`` off a facet dict and applies the rules
declared in ``sdd_core/data/facet_promotion_rules.yaml`` to compute a
promoted score. Read-only — the writer (existing
``review_quality.scoring`` pipeline) decides whether to apply.
"""
from __future__ import annotations

from typing import Any, Callable

from sdd_core.facet_promotion import PromotionRule, load_rules

from .constants import (
    MATCH_KIND_ADDRESSED_COUNT_EQUALS_OPEN,
    MATCH_KIND_CONSECUTIVE_CYCLES_WITH_NEW,
    PROMOTION_SEVERITY_ORDER,
    RULE_LOOP_BREAKER,
    RULE_PARTIAL_TO_PASS,
    SCORE_PASS,
    SCORE_PARTIAL,
    STATUS_ADDRESSED,
    STATUS_OPEN,
    STATUS_REPLACED,
    STATUS_STILL_OPEN,
)

__all__ = [
    "derive_facet_score",
    "cap_new_issue_severity",
    "PROMOTION_SEVERITY_ORDER",
]


def _addressed_in_cycle(history: list[dict], cycle: int) -> int:
    return sum(
        1 for h in history
        if isinstance(h, dict)
        and int(h.get("cycle") or 0) == cycle
        and h.get("status") == STATUS_ADDRESSED
    )


def _issues_in_cycle(history: list[dict], cycle: int) -> list[dict]:
    return [
        h for h in history
        if isinstance(h, dict) and int(h.get("cycle") or 0) == cycle
    ]


def _max_cycle(history: list[dict]) -> int:
    return max(
        (int(h.get("cycle") or 0) for h in history if isinstance(h, dict)),
        default=0,
    )


def _previous_open_count(history: list[dict], previous_cycle: int) -> int:
    return sum(
        1 for h in _issues_in_cycle(history, previous_cycle)
        if h.get("status") in (None, STATUS_OPEN, STATUS_STILL_OPEN)
    )


def _matches_addressed_count_equals_open(
    facet: dict, history: list[dict], pre: dict,
) -> bool:
    if pre.get("previous_score") and facet.get("score") != pre["previous_score"]:
        return False
    latest = _max_cycle(history)
    if latest <= 1:
        return False
    previous = latest - 1
    open_count = _previous_open_count(history, previous)
    if open_count < int(pre.get("previous_open_issues_count_min", 1) or 1):
        return False
    return _addressed_in_cycle(history, latest) == open_count


def _matches_consecutive_cycles_with_new(
    facet: dict, history: list[dict], pre: dict,
) -> bool:
    threshold = int(pre.get("consecutive_cycles_with_new_findings_min", 3) or 3)
    cycles_with_new: list[int] = []
    for cycle in range(1, _max_cycle(history) + 1):
        cycle_issues = _issues_in_cycle(history, cycle)
        if any(
            h.get("status") not in (STATUS_ADDRESSED, STATUS_REPLACED)
            for h in cycle_issues
        ):
            cycles_with_new.append(cycle)
    return len(cycles_with_new) >= threshold


_MATCHERS: dict[str, Callable[[dict, list[dict], dict], bool]] = {
    MATCH_KIND_ADDRESSED_COUNT_EQUALS_OPEN: _matches_addressed_count_equals_open,
    MATCH_KIND_CONSECUTIVE_CYCLES_WITH_NEW: _matches_consecutive_cycles_with_new,
}


# Rule evaluation order. Loop-breaker fires before partial→pass so that
# the Nth-cycle-with-new-findings cap holds even when the cycle's
# findings happen to all be addressed.
_RULE_PRIORITY: tuple[str, ...] = (RULE_LOOP_BREAKER, RULE_PARTIAL_TO_PASS)


def _rule_matches(rule: PromotionRule, facet: dict, history: list[dict]) -> bool:
    matcher = _MATCHERS.get(rule.match_kind)
    if matcher is None:
        return False
    return matcher(facet, history, rule.preconditions)


def derive_facet_score(facet: dict) -> str:
    """Return the promoted score for *facet* (or its current score)."""
    history = facet.get("cited_issues_history") or []
    if not isinstance(history, list) or not history:
        return facet.get("score", "")
    rules = load_rules()
    for rule_name in _RULE_PRIORITY:
        rule = rules.get(rule_name)
        if not rule or not _rule_matches(rule, facet, history):
            continue
        con = rule.consequence
        if con.get("block_promotion"):
            return facet.get("score", "")
        new_score = con.get("new_score")
        if new_score:
            return str(new_score)
    return facet.get("score", "")


def cap_new_issue_severity(facet: dict, severity: str) -> str:
    """Return *severity* clipped down to the rule's
    ``new_issues_severity_cap`` when promotion fires.
    """
    history = facet.get("cited_issues_history") or []
    if not history:
        return severity
    rules = load_rules()
    rule = rules.get(RULE_PARTIAL_TO_PASS)
    if not rule or not _rule_matches(rule, facet, history):
        return severity
    loop_breaker = rules.get(RULE_LOOP_BREAKER)
    if loop_breaker and _rule_matches(loop_breaker, facet, history):
        return severity
    cap = rule.consequence.get("new_issues_severity_cap")
    if not cap or cap not in PROMOTION_SEVERITY_ORDER:
        return severity
    cap_idx = PROMOTION_SEVERITY_ORDER.index(cap)
    sev_idx = (
        PROMOTION_SEVERITY_ORDER.index(severity)
        if severity in PROMOTION_SEVERITY_ORDER
        else cap_idx
    )
    return PROMOTION_SEVERITY_ORDER[min(cap_idx, sev_idx)]
