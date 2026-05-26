"""Typed substrate for pipeline envelopes and actions.

Single vocabulary of action kinds, severities, and envelope shape so
phases and downstream adapters normalise ``required_tool_calls`` onto
one mirror instead of reshaping every phase module again.

Kept deliberately dependency-free (only stdlib + sdd_core) so it can
be imported from any layer — phases, adapters, tests,
``pipeline-tick`` dispatcher, lints. Existing phases still emit
``required_tool_calls[]`` dicts directly; the typed mirror here is
the migration target.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

__all__ = [
    "ENVELOPE_VERSION",
    "Severity",
    "ActionKind",
    "Action",
    "Envelope",
    "envelope_to_dict",
]


# Monotonic envelope schema version. Additive field changes keep the
# version; removing or renaming a field bumps it. Bumped together
# with the paired `pipeline/manifest` capability handshake.
ENVELOPE_VERSION: int = 1


class Severity(str, Enum):
    """Severity level of an emitted action.

    A single vocabulary — recovery is not a parallel list but a
    severity tag on the same ``actions[]`` entries. The agent's tick
    loop treats every entry identically; only the pipeline decides
    terminality via ``Envelope.terminal``.
    """

    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    RECOVER = "recover"
    # Entry the active harness cannot execute. Renderers MUST hide
    # ``severity: skip`` entries from the agent to prevent trial-and-
    # error. Emitted by :meth:`review.actions.Action.todo_write` when
    # the adapter exposes no TODO surface.
    SKIP = "skip"


class ActionKind(str, Enum):
    """Closed enum of action kinds an envelope can emit.

    Adding a kind is a one-line edit plus a paired host-side adapter
    registration. Lists stay alphabetical for deterministic
    serialisation / diffing.
    """

    ASK_QUESTION = "AskQuestion"
    INSTRUCTION = "Instruction"
    PARALLEL_GROUP = "ParallelGroup"
    PIPELINE_TICK = "PipelineTick"
    SHELL_PROBE = "ShellProbe"
    TASK = "Task"
    TODO_WRITE = "TodoWrite"


@dataclass(frozen=True)
class Action:
    """Typed action entry on an envelope.

    ``payload`` is an opaque dict the host adapter for ``kind`` knows
    how to interpret (e.g. a ``TodoWrite`` payload or an
    ``AskQuestion`` ``{prompt_type, params}`` pair). Keeping the
    payload untyped at this layer lets each host adapter add
    structure per-kind without churning every call site at once.
    """

    kind: ActionKind
    payload: dict[str, Any] = field(default_factory=dict)
    severity: Severity = Severity.INFO
    reason: str = ""


@dataclass
class Envelope:
    """Typed envelope returned by a ``pipeline/tick`` invocation.

    ``actions`` is the **only** action collection on the envelope —
    there is no parallel ``recovery_actions`` list. Recovery steps
    are simply entries with ``severity = RECOVER``. ``terminal`` is
    the sole stop signal.
    """

    gate_id: str
    phase_from: str
    phase_to: str
    actions: list[Action] = field(default_factory=list)
    terminal: bool = False
    envelope_version: int = ENVELOPE_VERSION
    trace: dict[str, Any] = field(default_factory=dict)


def envelope_to_dict(env: Envelope) -> dict[str, Any]:
    """Serialise an :class:`Envelope` to a JSON-ready dict.

    Uses :func:`dataclasses.asdict` so enum values flow through the
    ``str(Enum)`` mixin — no custom encoder needed. Exported as a
    helper (rather than via ``json.dumps(asdict(env))``) so the
    enum-coercion rule has exactly one callsite.
    """
    raw = asdict(env)
    # Coerce the enum-backed string fields so downstream consumers
    # receive the wire value (``"info"``, ``"TodoWrite"``) rather than
    # ``Severity.INFO`` / ``ActionKind.TODO_WRITE`` object reprs.
    for action in raw.get("actions") or ():
        kind = action.get("kind")
        if isinstance(kind, ActionKind):
            action["kind"] = kind.value
        severity = action.get("severity")
        if isinstance(severity, Severity):
            action["severity"] = severity.value
    return raw
