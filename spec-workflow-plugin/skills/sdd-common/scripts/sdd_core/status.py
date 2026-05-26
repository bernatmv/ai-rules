"""Document / overall review status values — single source of truth."""
from __future__ import annotations

from enum import Enum

__all__ = ["DocStatus"]


class DocStatus(str, Enum):
    """Document / overall review status values.

    Inherits from ``str`` so ``DocStatus.PASS == "PASS"`` is True and
    JSON serialization works without a custom encoder.
    """
    PASS = "PASS"
    FAIL = "FAIL"
    NEEDS_WORK = "NEEDS_WORK"
    INCOMPLETE = "INCOMPLETE"
    WARNING = "WARNING"
