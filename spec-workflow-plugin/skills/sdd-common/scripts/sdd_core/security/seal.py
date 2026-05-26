"""Post-boot policy seal for the security registry.

The pipeline-tick startup wires every primitive (actor policy, locked
store, runner allowlist, security config, audit sink, hasher, dry-run
gate) and then calls :func:`seal_security`. After the seal every
``Seam.set`` raises :exc:`RuntimeError` so a mid-pipeline mutation
attempt fails loudly.

Tests narrow the seal via the package-private :func:`_unsealed`
context manager; production code must never import it.
"""
from __future__ import annotations

import contextlib
from typing import Iterator

from . import _seam

__all__ = ["seal_security", "is_sealed", "_unsealed"]


def is_sealed() -> bool:
    return _seam._get_sealed()


def seal_security() -> None:
    """Lock every registered seam against further mutation.

    Idempotent — re-sealing a sealed registry is a no-op.
    """
    _seam._set_sealed(True)


@contextlib.contextmanager
def _unsealed() -> Iterator[None]:
    """Test-only — unseal for the duration of the block, then restore."""
    prior = _seam._get_sealed()
    _seam._set_sealed(False)
    try:
        yield
    finally:
        _seam._set_sealed(prior)
