"""Canonical exit-code policy for SDD scripts.

Every non-failure outcome collapses to **exit 0** with
``status: "result"``. Outcomes (search miss, partial coverage,
preflight gate, etc.) travel in the JSON envelope under
``data.outcome`` — see :data:`RESULT_OUTCOMES` for the registry.
Reserve non-zero exit codes for genuine failures: ``USER_ERROR``
(bad args / validation fail) and ``SYSTEM_FAULT`` (permissions,
disk, corrupt internal state).
"""
from __future__ import annotations

from enum import IntEnum

__all__ = ["ExitClass", "RESULT_OUTCOMES"]


class ExitClass(IntEnum):
    OK = 0
    USER_ERROR = 1
    SYSTEM_FAULT = 2


RESULT_OUTCOMES = frozenset({"miss", "partial", "preflight_required"})
