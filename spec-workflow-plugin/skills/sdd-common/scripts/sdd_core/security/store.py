"""Pluggable locked-store seam.

Default factory wraps :class:`TransactionalStore`. Auditors who
prescribe different lock semantics (NFS-safe, Windows, region-level,
``fcntl``-with-timeout) plug a fresh factory via
:func:`set_locked_store_factory`; call sites read through
:func:`locked_store` and never bind to a concrete class.

Versioned protocol — setters refuse implementations whose
``protocol_version`` is below the bundled version so a future API
extension cannot be silently downgraded by an older third-party impl.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Callable, ClassVar, Protocol, runtime_checkable

from .state import TransactionalStore as _TransactionalStore
from ._seam import FactorySeam

__all__ = [
    "LockedStore",
    "PROTOCOL_VERSION",
    "TransactionalStore",
    "locked_store",
    "set_locked_store_factory",
    "reset_locked_store_factory",
]

PROTOCOL_VERSION = 1


@runtime_checkable
class LockedStore(Protocol):
    protocol_version: int

    def __enter__(self) -> "LockedStore": ...
    def __exit__(self, exc_type, exc, tb) -> bool: ...
    def read_json(self, default: Any = None) -> Any: ...
    def read_bytes(self, default: "bytes | None" = None) -> "bytes | None": ...
    def write_json(self, content: dict, *, verify_key: "str | None" = None) -> None: ...
    def append_line(self, line: str) -> None: ...


class TransactionalStore(_TransactionalStore):
    """Bundled :class:`LockedStore` implementation with class-level version."""

    protocol_version: ClassVar[int] = PROTOCOL_VERSION


def _default_factory(path: "str | Path") -> LockedStore:
    return TransactionalStore(path)  # type: ignore[return-value]


def _probe_path() -> Path:
    return Path(tempfile.gettempdir()) / ".sdd_security_locked_store_probe"


def _probe_cleanup(path: Any) -> None:
    p = Path(os.fspath(path))
    if p.exists():
        os.remove(p)


_seam: FactorySeam[LockedStore] = FactorySeam(
    name="LockedStoreFactory",
    protocol=LockedStore,
    default_factory=_default_factory,
    protocol_version=PROTOCOL_VERSION,
    probe_arg_factory=_probe_path,
    probe_cleanup=_probe_cleanup,
)


def locked_store(path: "str | Path") -> LockedStore:
    return _seam.get()(path)


def set_locked_store_factory(
    factory: Callable[["str | Path"], LockedStore],
) -> None:
    """Install a new locked-store factory.

    Validates structural conformance and protocol version on a probe
    path so a misconfigured factory fails at setup, not at first use.
    """
    _seam.set(factory)


def reset_locked_store_factory() -> None:
    _seam.reset()
