"""Phase + Validator Protocols for graph-driven dispatch.

The workflow graph at ``sdd_core/data/workflow-graph.json`` declares
what each phase consumes / produces / fires; the Protocols here are the
runtime contract every phase module and validator function honours.

* :class:`Phase` — the dispatch unit. ``id`` matches the graph entry's
  ``id``; ``run(ctx, args)`` is the entry point the dispatcher invokes.
* :class:`Validator` — the precondition / validation unit. The graph
  references validators by id; each id must resolve to a registered
  function in :mod:`sdd_core.validators`. ``check(ctx, args)`` returns
  a :class:`ValidatorResult` whose ``ok`` flag drives the gate.

These are pure typing surfaces — no concrete implementations live in
this module.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, runtime_checkable

__all__ = [
    "ValidatorResult",
    "Phase",
    "Validator",
]


@dataclass(frozen=True)
class ValidatorResult:
    """One validator's verdict.

    ``ok`` drives the gate. ``code`` is a stable identifier for the
    failure (used by the agent to route remediation). ``message`` is the
    human-readable summary; ``details`` is structured payload the
    success / preflight envelope can carry.
    """

    ok: bool
    code: str = ""
    message: str = ""
    details: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "code": self.code,
            "message": self.message,
            "details": dict(self.details),
        }


@runtime_checkable
class Phase(Protocol):
    """Runtime contract for a workflow phase.

    Implementations live as one module per phase under
    :mod:`sdd_core.pipeline_phases` and expose:

    * ``id`` — module-level string matching the workflow graph entry.
    * ``run(ctx, args)`` — the dispatch entry point. Returns a JSON-
      serialisable dict the dispatcher embeds in the success envelope.

    The graph entry's ``preconditions`` and ``validations`` resolve to
    :class:`Validator` functions; phases never re-implement them.
    """

    id: str

    def run(
        self,
        ctx: Any,
        args: argparse.Namespace,
    ) -> dict: ...


@runtime_checkable
class Validator(Protocol):
    """Runtime contract for a workflow validator.

    Each validator is a registered function under
    :mod:`sdd_core.validators`. The graph references validators by id;
    the cross-refs lint asserts every referenced id resolves.

    ``check`` returns a :class:`ValidatorResult` rather than raising so
    the dispatcher can roll up multiple validator outcomes into one
    gate decision.
    """

    id: str

    def check(
        self,
        ctx: Any,
        args: argparse.Namespace | None = None,
    ) -> ValidatorResult: ...
