"""Canonical approval action vocabulary + aliases."""
from __future__ import annotations

__all__ = [
    "CANONICAL_ACTIONS",
    "ACTION_ALIASES",
    "STATUS_TRANSITIONS",
    "canonical_action",
    "status_choices",
]


CANONICAL_ACTIONS: tuple[str, ...] = ("approve", "reject", "needs_revision")

ACTION_ALIASES: dict[str, str] = {
    "approve": "approve",
    "approved": "approve",
    "reject": "reject",
    "rejected": "reject",
    "needs_revision": "needs_revision",
    "needs-revision": "needs_revision",
}

# Canonical action -> persisted approval status. Single source of truth so
# scripts that write the new status do not redeclare the mapping.
STATUS_TRANSITIONS: dict[str, str] = {
    "approve": "approved",
    "reject": "rejected",
    "needs_revision": "needs_revision",
}


def status_choices() -> list[str]:
    """Return every accepted ``--status`` value in canonical + alias form."""
    return sorted(ACTION_ALIASES.keys())


def canonical_action(raw: "str | None") -> "str | None":
    """Normalise an action synonym to its canonical form."""
    if raw is None:
        return None
    return ACTION_ALIASES.get(raw)
