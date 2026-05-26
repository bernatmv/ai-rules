"""Lazy aliases over :func:`security_config`.

Every public symbol resolves through the active ``SecurityConfig`` at
read time. Module-level ``Final[str]`` literals are gone — the source
of truth is the dataclass on the seam, so an
``override_security_config(...)`` block flips the values
constants.X reports for the duration of the override.

PEP 562 ``__getattr__`` makes module-level ``constants.HUMAN_APPROVAL_ENV``
work without sprinkling ``security_config().HUMAN_APPROVAL_ENV`` at
every call site.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, FrozenSet

if TYPE_CHECKING:
    HUMAN_APPROVAL_ENV: str
    HUMAN_APPROVAL_VALUE: str
    DRY_RUN_ENV: str
    DRY_RUN_ON_VALUE: str
    TRUTHY_ENV_VALUES: FrozenSet[str]
    ACTOR_POLICY_OVERRIDE_ENV: str
    ACTOR_OVERRIDE_ALWAYS_HUMAN: str
    ACTOR_OVERRIDE_ALWAYS_AGENT: str
    SUBPROCESS_DEFAULT_TIMEOUT_SECS: int
    SUBPROCESS_MAX_PARSE_BYTES: int
    SUBPROCESS_FORBIDDEN_CHARS: FrozenSet[str]
    EXTRA_RUNNERS_ENV: str
    IDENTIFIER_REGEX: str
    AUDIT_HASH_ALGO: str

_FIELDS = frozenset({
    "HUMAN_APPROVAL_ENV",
    "HUMAN_APPROVAL_VALUE",
    "DRY_RUN_ENV",
    "DRY_RUN_ON_VALUE",
    "TRUTHY_ENV_VALUES",
    "ACTOR_POLICY_OVERRIDE_ENV",
    "ACTOR_OVERRIDE_ALWAYS_HUMAN",
    "ACTOR_OVERRIDE_ALWAYS_AGENT",
    "SUBPROCESS_DEFAULT_TIMEOUT_SECS",
    "SUBPROCESS_MAX_PARSE_BYTES",
    "SUBPROCESS_FORBIDDEN_CHARS",
    "EXTRA_RUNNERS_ENV",
    "IDENTIFIER_REGEX",
    "AUDIT_HASH_ALGO",
})


def __getattr__(name: str) -> Any:  # PEP 562
    if name in _FIELDS:
        from .config import security_config
        return getattr(security_config(), name)
    raise AttributeError(f"module 'constants' has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(_FIELDS)


__all__ = sorted(_FIELDS)
