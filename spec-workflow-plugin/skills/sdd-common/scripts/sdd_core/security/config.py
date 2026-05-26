"""Pluggable security configuration seam.

A frozen dataclass owns every cross-cutting security literal. Auditors
who prescribe stricter forbidden-chars / shorter timeouts / FIPS regex
pass a fresh instance into :func:`set_security_config`; tests narrow
with :func:`override_security_config`.

The legacy :mod:`sdd_core.security.constants` module remains the
read-side surface — every value resolves through this seam so
downstream callers do not need to know whether the literal lives on a
module or a frozen dataclass.
"""
from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from typing import FrozenSet, Iterator, Protocol, runtime_checkable

from ._seam import Seam

__all__ = [
    "SecurityConfig",
    "SecurityConfigProtocol",
    "PROTOCOL_VERSION",
    "security_config",
    "set_security_config",
    "reset_security_config",
    "override_security_config",
]

PROTOCOL_VERSION = 1


@dataclass(frozen=True)
class SecurityConfig:
    """Single source of truth for every cross-cutting security literal."""

    HUMAN_APPROVAL_ENV: str = "SDD_HUMAN_APPROVAL"
    HUMAN_APPROVAL_VALUE: str = "1"
    DRY_RUN_ENV: str = "SDD_PIPELINE_DRY_RUN"
    DRY_RUN_ON_VALUE: str = "1"
    TRUTHY_ENV_VALUES: FrozenSet[str] = field(
        default_factory=lambda: frozenset({"1", "true", "yes", "on"}),
    )
    ACTOR_POLICY_OVERRIDE_ENV: str = "SDD_ACTOR_POLICY_OVERRIDE"
    ACTOR_OVERRIDE_ALWAYS_HUMAN: str = "always-human"
    ACTOR_OVERRIDE_ALWAYS_AGENT: str = "always-agent"
    SUBPROCESS_DEFAULT_TIMEOUT_SECS: int = 120
    SUBPROCESS_MAX_PARSE_BYTES: int = 2 * 1024 * 1024
    SUBPROCESS_FORBIDDEN_CHARS: FrozenSet[str] = field(
        default_factory=lambda: frozenset(";&|`$><\n\r\\"),
    )
    EXTRA_RUNNERS_ENV: str = "SDD_EXTRA_RUNNERS"
    IDENTIFIER_REGEX: str = r"^[A-Za-z0-9_][A-Za-z0-9._-]{0,127}$"
    AUDIT_HASH_ALGO: str = "sha256"
    protocol_version: int = PROTOCOL_VERSION


@runtime_checkable
class SecurityConfigProtocol(Protocol):
    protocol_version: int
    HUMAN_APPROVAL_ENV: str
    HUMAN_APPROVAL_VALUE: str
    DRY_RUN_ENV: str
    TRUTHY_ENV_VALUES: FrozenSet[str]
    SUBPROCESS_FORBIDDEN_CHARS: FrozenSet[str]
    SUBPROCESS_DEFAULT_TIMEOUT_SECS: int
    IDENTIFIER_REGEX: str
    AUDIT_HASH_ALGO: str


_seam: Seam[SecurityConfig] = Seam(
    name="SecurityConfig",
    protocol=SecurityConfigProtocol,
    default=SecurityConfig(),
    protocol_version=PROTOCOL_VERSION,
)

security_config = _seam.get


def set_security_config(cfg: SecurityConfig) -> None:
    _seam.set(cfg)


def reset_security_config() -> None:
    _seam.reset()


@contextlib.contextmanager
def override_security_config(cfg: SecurityConfig) -> Iterator[None]:
    """Test-only narrow override that restores the prior config on exit."""
    prior = _seam.get()
    set_security_config(cfg)
    try:
        yield
    finally:
        _seam._active = prior  # type: ignore[attr-defined]
