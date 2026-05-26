"""Pluggable dry-run gate.

Today every primitive reads :envvar:`SDD_PIPELINE_DRY_RUN` inline via
:func:`sdd_core.output._dry_run_active`. An attacker (or a stray test)
that mutates the env mid-pipeline therefore changes the gate state
between two RMW operations. Resolution: a Protocol with one method
(:meth:`is_dry_run`) and a bundled default that snapshots the env once
at process boot.

Tests pass :class:`AlwaysDry` / :class:`NeverDry` instances; production
wires :class:`EnvDryRunGate` at startup and threads the gate via the
context objects.
"""
from __future__ import annotations

import os
from typing import Protocol, runtime_checkable

from . import config
from ._seam import Seam

__all__ = [
    "DryRunGate",
    "PROTOCOL_VERSION",
    "EnvDryRunGate",
    "AlwaysDry",
    "NeverDry",
    "dry_run_gate",
    "set_dry_run_gate",
    "reset_dry_run_gate",
]

PROTOCOL_VERSION = 1


@runtime_checkable
class DryRunGate(Protocol):
    protocol_version: int

    def is_dry_run(self) -> bool: ...


class EnvDryRunGate:
    """Default gate — snapshots :envvar:`SDD_PIPELINE_DRY_RUN` at construction."""

    protocol_version = PROTOCOL_VERSION

    def __init__(self) -> None:
        cfg = config.security_config()
        raw = os.environ.get(cfg.DRY_RUN_ENV, "")
        self._snapshot = raw.strip().lower() in cfg.TRUTHY_ENV_VALUES

    def is_dry_run(self) -> bool:
        return self._snapshot


class AlwaysDry:
    protocol_version = PROTOCOL_VERSION

    def is_dry_run(self) -> bool:
        return True


class NeverDry:
    protocol_version = PROTOCOL_VERSION

    def is_dry_run(self) -> bool:
        return False


_seam: Seam[DryRunGate] = Seam(
    name="DryRunGate",
    protocol=DryRunGate,
    default_factory=EnvDryRunGate,
    protocol_version=PROTOCOL_VERSION,
)

dry_run_gate = _seam.get


def set_dry_run_gate(gate: DryRunGate) -> None:
    _seam.set(gate)


def reset_dry_run_gate() -> None:
    _seam.reset()
