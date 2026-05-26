"""Pluggable hashing seam.

A single Protocol fronts every file/content hash so a FIPS prescription
("SHA-512 only", "BLAKE2b only") becomes one new class file plus one
:func:`set_hasher` call. The bundled default delegates to
:func:`sdd_core.reference_ledger.hash_file` so existing callers see no
behaviour change.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Protocol, runtime_checkable

from ._seam import Seam

__all__ = [
    "Hasher",
    "PROTOCOL_VERSION",
    "hasher",
    "set_hasher",
    "reset_hasher",
]

PROTOCOL_VERSION = 1


@runtime_checkable
class Hasher(Protocol):
    protocol_version: int
    algo: str

    def hash_file(self, path: "str | Path") -> str: ...
    def hash_bytes(self, data: bytes) -> str: ...


class _Sha256Hasher:
    """Bundled default — delegates to the ledger's existing hash helper."""

    protocol_version = PROTOCOL_VERSION
    algo = "sha256"

    def hash_file(self, path: "str | Path") -> str:
        from sdd_core.reference_ledger import hash_file as _ledger_hash
        return _ledger_hash(path)

    def hash_bytes(self, data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()


def _require_algo(h: Hasher) -> None:
    if not getattr(h, "algo", ""):
        raise TypeError("Hasher.algo must be a non-empty string")


_seam: Seam[Hasher] = Seam(
    name="Hasher",
    protocol=Hasher,
    default=_Sha256Hasher(),
    protocol_version=PROTOCOL_VERSION,
    extra_validator=_require_algo,
)

hasher = _seam.get


def set_hasher(h: Hasher) -> None:
    _seam.set(h)


def reset_hasher() -> None:
    _seam.reset()
