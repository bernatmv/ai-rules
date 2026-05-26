"""Shared lint-issue presentation helpers.

Centralises the per-doc lint truncation policy so ``spec/lint-*.py``
shims emit identical inline-context shapes (``issues[:N]`` plus a
``truncated`` flag). Single source of truth for the cap value.
"""
from __future__ import annotations

from typing import Iterable, TypeVar

__all__ = [
    "MAX_CONTEXT_ISSUES",
    "truncate_issues_for_context",
]


MAX_CONTEXT_ISSUES = 30

T = TypeVar("T")


def truncate_issues_for_context(
    issues: Iterable[T], *, limit: int = MAX_CONTEXT_ISSUES,
) -> tuple[list[T], bool]:
    """Return ``(head, truncated)`` for inline error-envelope context.

    ``head`` is at most *limit* items; ``truncated`` is ``True`` when
    the original list exceeded the cap. Callers persist the full list
    via the findings file and surface only the head inline so stderr
    payloads stay readable in standard 120-column terminals.
    """
    materialised = list(issues)
    if len(materialised) <= limit:
        return materialised, False
    return materialised[:limit], True
