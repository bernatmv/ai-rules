"""Pluggable runner-allowlist seam for :mod:`subprocess_safe`.

Forks (Rust, Elixir, internal runners) compose
:func:`register_runner` rather than editing the bundled tuple. The
default allowlist remains the single source of truth for the public
plugin; registrations stack additively.

Operators who cannot ship a Python shim drop a comma-separated
``runner:subcommand`` list into :envvar:`SDD_EXTRA_RUNNERS` (parsed
once at module import).
"""
from __future__ import annotations

import os
from typing import Iterable, Protocol, Sequence, runtime_checkable

from . import constants
from ._seam import Seam
from .subprocess_safe import ALLOWED_RUNNERS as _BUNDLED

__all__ = [
    "RunnerAllowlist",
    "PROTOCOL_VERSION",
    "default_allowlist",
    "register_runner",
    "set_allowlist",
    "reset_allowlist",
]

PROTOCOL_VERSION = 1


@runtime_checkable
class RunnerAllowlist(Protocol):
    protocol_version: int

    def is_allowed(self, argv: Sequence[str]) -> bool: ...


class _PrefixAllowlist:
    """Bundled default — exact-prefix match against a tuple of tuples."""

    protocol_version = PROTOCOL_VERSION

    def __init__(self, prefixes: Iterable[tuple[str, ...]]) -> None:
        self._prefixes: tuple[tuple[str, ...], ...] = tuple(prefixes)

    def is_allowed(self, argv: Sequence[str]) -> bool:
        return any(
            list(argv[: len(p)]) == list(p) for p in self._prefixes
        )


def _parse_extra_runners(raw: str) -> tuple[tuple[str, ...], ...]:
    out: list[tuple[str, ...]] = []
    for entry in raw.split(","):
        prefix = tuple(tok for tok in entry.strip().split(":") if tok)
        if prefix:
            out.append(prefix)
    return tuple(out)


_seam: Seam[RunnerAllowlist] = Seam(
    name="RunnerAllowlist",
    protocol=RunnerAllowlist,
    default=_PrefixAllowlist(
        (*_BUNDLED, *_parse_extra_runners(os.environ.get(constants.EXTRA_RUNNERS_ENV, ""))),
    ),
    protocol_version=PROTOCOL_VERSION,
)

default_allowlist = _seam.get


def set_allowlist(allowlist: RunnerAllowlist) -> None:
    _seam.set(allowlist)


def register_runner(prefix: tuple[str, ...]) -> None:
    """Stack a fresh runner prefix onto the bundled default.

    Refuses to compose onto an opaque custom strategy — registering on
    something whose composition rules we don't own would silently
    no-op. Operators with a custom strategy must use
    :func:`set_allowlist` instead.
    """
    if not prefix or any(not tok for tok in prefix):
        raise ValueError(f"Invalid runner prefix: {prefix!r}")
    current = _seam.get()
    if not isinstance(current, _PrefixAllowlist):
        raise TypeError(
            "register_runner only composes onto the default _PrefixAllowlist; "
            "use set_allowlist() to install a fully custom strategy."
        )
    if prefix in current._prefixes:
        return
    _seam.set(_PrefixAllowlist((*current._prefixes, prefix)))


def reset_allowlist() -> None:
    _seam.set(_PrefixAllowlist(_BUNDLED))
