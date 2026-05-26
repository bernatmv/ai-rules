"""Typed views over the gate-session payload.

The on-disk schema (``1.0.0``) keeps one gate per session file under
the flat ``review_gate`` key. The dataclasses here present that shape
as a typed view: :class:`WorkflowSession` aggregates the session-level
fields, :class:`GateSession` wraps the active gate, and
:meth:`WorkflowSession.from_session_dict` / :meth:`to_session_dict`
round-trip the existing dict shape byte-identically.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

from ..constants import SCOPE_PER_DOCUMENT

__all__ = [
    "Todo",
    "PhaseSnapshot",
    "GateSession",
    "WorkflowSession",
]


@dataclass
class Todo:
    """One tracker entry on a :class:`GateSession`.

    Mirrors the agent-facing TodoWrite shape exactly so
    :meth:`GateSession.to_session_dict` emits the same dict the live
    session file holds today — no serde drift.
    """

    id: str
    content: str = ""
    status: str = "pending"

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Todo":
        return cls(
            id=str(raw.get("id", "")),
            content=str(raw.get("content", "") or ""),
            status=str(raw.get("status", "pending") or "pending"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "status": self.status,
        }


@dataclass
class PhaseSnapshot:
    """Idempotency cache for one phase tick.

    Reflects the shape written by :func:`review_quality.gate_session.
    cache.set_phase_snapshot`. Values are stored verbatim — the
    dataclass wraps the dict for typed access without rewriting
    on-disk layout.
    """

    key: str = ""
    inputs: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "PhaseSnapshot":
        return cls(
            key=str(raw.get("key", "") or ""),
            inputs=dict(raw.get("inputs") or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"key": self.key, "inputs": dict(self.inputs)}


@dataclass
class GateSession:
    """Typed view of one review gate inside a session file.

    Carries the fields the pipeline mutates during a review gate run
    (phase, owned TODOs, pending tool calls, idempotency snapshots).
    :meth:`from_dict` / :meth:`to_dict` operate on the live
    ``review_gate`` + ``phase_snapshots`` shape so no on-disk
    migration is required for single-gate sessions.
    :attr:`owned_todo_ids` is the declarative authority on the
    session-side; the emitted envelope carries the same list so
    ``Phase._post_process`` can consume it without reaching through
    a raw dict.
    """

    gate_id: str = ""
    gate_uuid: Optional[str] = None
    parent_todo_id: Optional[str] = None
    parent_todo_content: Optional[str] = None
    phase: Optional[str] = None
    current_state: Optional[str] = None
    fix_cycle: int = 0
    # Stale-doc re-entry counter — bumped by ``pre_approval`` when
    # docs were modified after their last review. Kept separate from
    # ``fix_cycle`` so the bounded ``max_fix_cycles`` contract stays
    # literal.
    reentry_count: int = 0
    max_cycles: int = 3
    review_scope: str = SCOPE_PER_DOCUMENT
    owned_todo_ids: frozenset[str] = field(default_factory=frozenset)
    todos: list[Todo] = field(default_factory=list)
    pending_tool_calls: list[dict] = field(default_factory=list)
    executed_tool_calls_signatures: list[str] = field(default_factory=list)
    phase_snapshots: dict[str, PhaseSnapshot] = field(default_factory=dict)
    terminal_state: Optional[str] = None
    terminal_reason: Optional[str] = None
    user_accepted_at: Optional[str] = None

    @classmethod
    def from_dict(
        cls, review_gate: dict[str, Any],
        *, phase_snapshots: Optional[dict[str, Any]] = None,
    ) -> "GateSession":
        """Materialise a :class:`GateSession` from the raw ``review_gate``
        dict and the session-level ``phase_snapshots`` block.

        ``phase_snapshots`` is stored one level up in the session file
        (sibling to ``review_gate``), so it is passed in separately.
        """
        active = [
            Todo.from_dict(t)
            for t in (review_gate.get("active_todos") or [])
            if isinstance(t, dict)
        ]
        # ``owned_todo_ids`` is computed on emit (see
        # :func:`review_quality.todo_lifecycle.build_owned_todo_ids`).
        # The typed view simply stages the frozenset so downstream
        # namespace-scope checks have one accessor.
        owned: Iterable[str] = review_gate.get("owned_todo_ids") or ()
        snaps = {
            name: PhaseSnapshot.from_dict(snap or {})
            for name, snap in (phase_snapshots or {}).items()
            if isinstance(snap, dict)
        }
        return cls(
            gate_id=str(review_gate.get("gate_id") or ""),
            gate_uuid=review_gate.get("gate_uuid"),
            parent_todo_id=review_gate.get("parent_todo_id"),
            parent_todo_content=review_gate.get("parent_todo_content"),
            phase=review_gate.get("required_next_phase"),
            current_state=review_gate.get("current_state"),
            fix_cycle=int(review_gate.get("fix_cycle") or 0),
            reentry_count=int(review_gate.get("reentry_count") or 0),
            max_cycles=int(review_gate.get("max_cycles") or 3),
            review_scope=str(
                review_gate.get("review_scope") or SCOPE_PER_DOCUMENT
            ),
            owned_todo_ids=frozenset(str(x) for x in owned if x),
            todos=active,
            pending_tool_calls=list(
                review_gate.get("pending_tool_calls") or []
            ),
            executed_tool_calls_signatures=list(
                review_gate.get("executed_tool_calls_signatures") or []
            ),
            phase_snapshots=snaps,
            terminal_state=review_gate.get("terminal_state"),
            terminal_reason=review_gate.get("terminal_reason"),
            user_accepted_at=review_gate.get("user_accepted_at"),
        )

    def to_review_gate_dict(self) -> dict[str, Any]:
        """Return the ``review_gate`` dict shape the session file uses.

        Round-trips byte-identically with :meth:`from_dict` on the
        fields this dataclass models — any field not modelled stays
        under :class:`WorkflowSession`'s passthrough layer. Mirrors
        the on-disk canonical shape exactly so a :class:`GateSession`-backed
        write path can opt in without touching readers that still
        index the raw dict.
        """
        return {
            "gate_id": self.gate_id or None,
            "gate_uuid": self.gate_uuid,
            "parent_todo_id": self.parent_todo_id,
            "parent_todo_content": self.parent_todo_content,
            "fix_cycle": self.fix_cycle,
            "reentry_count": self.reentry_count,
            "max_cycles": self.max_cycles,
            "current_state": self.current_state,
            "required_next_phase": self.phase,
            "review_scope": self.review_scope,
            "active_todos": [t.to_dict() for t in self.todos],
            "pending_tool_calls": list(self.pending_tool_calls),
            "executed_tool_calls_signatures": list(
                self.executed_tool_calls_signatures
            ),
            "terminal_state": self.terminal_state,
            "terminal_reason": self.terminal_reason,
            "user_accepted_at": self.user_accepted_at,
        }


@dataclass
class WorkflowSession:
    """Typed view of the whole session file.

    Wraps the flat ``.gate-session.json`` shape — top-level metadata
    plus one active :class:`GateSession`. Single-gate sessions land
    as a single-entry dict keyed by ``gate.gate_id`` (or ``""``).
    :meth:`from_session_dict` / :meth:`to_session_dict` round-trip
    with the session payload.
    """

    schema_version: str = "1.0.0"
    category: Optional[str] = None
    target_name: Optional[str] = None
    workflow_mode: Optional[str] = None
    current_step: Optional[str] = None
    completed_gates: list[dict] = field(default_factory=list)
    started_at: Optional[str] = None
    updated_at: Optional[str] = None
    active_gates: dict[str, GateSession] = field(default_factory=dict)
    launch_args_cache: dict[str, Any] = field(default_factory=dict)
    single_doc_stop_marker: Optional[dict] = None
    _extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_session_dict(cls, session: dict[str, Any]) -> "WorkflowSession":
        """Materialise a :class:`WorkflowSession` from the session dict.

        Modelled fields land on the dataclass; any unknown keys land
        on :attr:`_extras` so the round-trip survives forward
        additions.
        """
        known = {
            "schema_version", "category", "target_name", "workflow_mode",
            "current_step", "completed_gates", "started_at", "updated_at",
            "review_gate", "launch_args_cache", "phase_snapshots",
            "single_doc_stop_marker",
        }
        extras = {k: v for k, v in session.items() if k not in known}
        review_gate = session.get("review_gate") or {}
        phase_snaps = session.get("phase_snapshots") or {}
        gate = GateSession.from_dict(
            review_gate if isinstance(review_gate, dict) else {},
            phase_snapshots=phase_snaps if isinstance(phase_snaps, dict) else None,
        )
        key = gate.gate_id or ""
        return cls(
            schema_version=str(session.get("schema_version") or "1.0.0"),
            category=session.get("category"),
            target_name=session.get("target_name"),
            workflow_mode=session.get("workflow_mode"),
            current_step=session.get("current_step"),
            completed_gates=list(session.get("completed_gates") or []),
            started_at=session.get("started_at"),
            updated_at=session.get("updated_at"),
            active_gates={key: gate},
            launch_args_cache=dict(session.get("launch_args_cache") or {}),
            single_doc_stop_marker=session.get("single_doc_stop_marker"),
            _extras=extras,
        )

    def to_session_dict(self) -> dict[str, Any]:
        """Emit the flat session dict from the typed view.

        Single-gate today: the first :class:`GateSession` in
        :attr:`active_gates` lands under ``review_gate`` and its
        ``phase_snapshots`` ride alongside at session level. Mirrors
        the canonical session shape so :func:`write_session` stays a drop-in.
        """
        if self.active_gates:
            # Stable iteration order: dict preserves insertion order in
            # CPython 3.7+, and ``from_session_dict`` inserts the one
            # gate with ``gate_id`` as key.
            gate = next(iter(self.active_gates.values()))
            review_gate = gate.to_review_gate_dict()
            phase_snaps = {
                name: snap.to_dict()
                for name, snap in gate.phase_snapshots.items()
            }
        else:
            review_gate = {}
            phase_snaps = {}
        out: dict[str, Any] = {
            "schema_version": self.schema_version,
            "category": self.category,
            "target_name": self.target_name,
            "workflow_mode": self.workflow_mode,
            "current_step": self.current_step,
            "completed_gates": list(self.completed_gates),
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "review_gate": review_gate,
            "launch_args_cache": dict(self.launch_args_cache),
            "phase_snapshots": phase_snaps,
            "single_doc_stop_marker": self.single_doc_stop_marker,
        }
        # Extras last so a forward-compatible field the view didn't
        # model cannot silently shadow a known key.
        for k, v in self._extras.items():
            out.setdefault(k, v)
        return out
