"""Harness-adapter registry.

Single authority mapping harness id → adapter instance. Callers prefer
:func:`sdd_core.harness.loader.load_adapter` (which reads
``harness.json``); ``get_adapter`` by name is exposed for tests and the
``SDD_HARNESS_OVERRIDE`` path.
"""
from __future__ import annotations

from .adapter import HarnessAdapter
from .adapters_claude_code import ClaudeCodeStandardAdapter
from .adapters_cursor import CursorAdapter
from .adapters_task_variant import ClaudeCodeTaskVariantAdapter

__all__ = [
    "ADAPTERS",
    "get_adapter",
    "available_adapter_names",
]


ADAPTERS: dict[str, HarnessAdapter] = {
    "cursor": CursorAdapter(),
    "claude-code-standard": ClaudeCodeStandardAdapter(),
    "claude-code-task-variant": ClaudeCodeTaskVariantAdapter(),
}


def get_adapter(name: str) -> HarnessAdapter:
    """Return the adapter registered under *name*.

    Raises ``KeyError`` with the list of available names when *name* is
    unknown so callers can surface a structured error to the user.
    Structural drift (an adapter that stops matching the
    :class:`HarnessAdapter` Protocol) surfaces as a loud
    :class:`TypeError` at lookup time so it never escapes to the wire.
    """
    if name not in ADAPTERS:
        raise KeyError(
            f"Unknown harness adapter {name!r}. "
            f"Available: {sorted(ADAPTERS.keys())}"
        )
    adapter = ADAPTERS[name]
    if not isinstance(adapter, HarnessAdapter):
        raise TypeError(
            f"Adapter {name!r} does not satisfy HarnessAdapter protocol"
        )
    return adapter


def available_adapter_names() -> tuple[str, ...]:
    return tuple(sorted(ADAPTERS.keys()))
