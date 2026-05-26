"""Safe-default adapter policy — single source of truth.

Keeping the safe-default adapter order and env-override resolution in
one module means the loader and health check consult the same policy
without re-implementing it inline. Operators can reshape the default
via ``SDD_HARNESS_DEFAULT`` (names one registered adapter) without
touching loader code.
"""
from __future__ import annotations

from typing import Mapping

from .registry import ADAPTERS

__all__ = [
    "DEFAULT_ADAPTER_ORDER",
    "resolve_safe_default",
    "SafeDefaultError",
]


DEFAULT_ADAPTER_ORDER: tuple[str, ...] = (
    "cursor",
    "claude-code-standard",
    "claude-code-task-variant",
)


class SafeDefaultError(ValueError):
    """Raised when ``SDD_HARNESS_DEFAULT`` names an unregistered adapter."""


def resolve_safe_default(env: Mapping[str, str]) -> str:
    """Return the safe-default adapter name.

    Reads ``SDD_HARNESS_DEFAULT`` first (operator override); falls back
    to the first registered name in :data:`DEFAULT_ADAPTER_ORDER`. Raises
    :class:`SafeDefaultError` when the env override names an unregistered
    adapter so detectors can surface it as an explicit contradiction.
    """
    raw = env.get("SDD_HARNESS_DEFAULT", "").strip()
    if raw:
        if raw not in ADAPTERS:
            raise SafeDefaultError(
                f"SDD_HARNESS_DEFAULT={raw!r} is not a registered adapter. "
                f"Available: {sorted(ADAPTERS.keys())}"
            )
        return raw
    for name in DEFAULT_ADAPTER_ORDER:
        if name in ADAPTERS:
            return name
    raise SafeDefaultError(
        "No registered adapter matches DEFAULT_ADAPTER_ORDER; "
        "registry is empty or mis-configured."
    )
