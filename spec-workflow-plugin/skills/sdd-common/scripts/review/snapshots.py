"""Per-phase typed snapshot dataclasses.

Single authority for the idempotency payloads each phase persists via
:func:`review_quality.gate_session.set_phase_snapshot`. Every subclass
of :class:`PhaseSnapshotBase` declares the concrete fields a given
phase replays from; serialisation is :func:`dataclasses.asdict` and
deserialisation is :meth:`cls.from_dict`.

Placement rationale: sibling of :mod:`review.schema` /
:mod:`review.transitions` under ``review/`` so snapshot shape lives
at the same single-authority-per-concept tier as the envelope schema
and the transition graph. Keeping every snapshot in one file lets
property tests walk every subclass without module discovery.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Any, ClassVar

__all__ = [
    "PhaseSnapshotBase",
    "PostReviewSnapshot",
    "PostFixSnapshot",
    "CheckRevalidationSnapshot",
    "snapshot_cls_for",
]


@dataclass(frozen=True)
class PhaseSnapshotBase:
    """Base for every per-phase typed snapshot.

    Subclasses declare their fields + class-level ``phase_name``.
    Serialisation is ``dataclasses.asdict``; deserialisation is
    :meth:`from_dict`, which filters ``raw`` to declared field names
    so sessions written before a field addition continue to round-trip
    (the missing field falls back to the subclass default).

    Frozen dataclass — snapshots are read-only once persisted so the
    replay path never races with a subsequent mutation.
    """

    phase_name: ClassVar[str] = ""

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict representation.

        Callers feed this into ``set_phase_snapshot`` under the
        session's ``phase_snapshots[phase_name].inputs`` key. The
        ``key`` field round-trips with the snapshot so replay sees
        the same cache key the original tick computed.
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict) -> "PhaseSnapshotBase":
        """Rebuild a snapshot from a session dict.

        Unknown keys are ignored; missing required fields surface as
        ``TypeError`` from the dataclass constructor.
        """
        field_names = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in raw.items() if k in field_names}
        return cls(**filtered)


@dataclass(frozen=True)
class PostReviewSnapshot(PhaseSnapshotBase):
    """Snapshot persisted by the ``post-review`` phase.

    Every field mirrors the ``inputs`` dict the untyped replay path
    wrote. ``required_tool_calls`` / ``todo_write_payload`` are the
    agent-facing passthrough fields; the remaining fields drive the
    routing shape :func:`review._routing.route_with_ack` rebuilds on
    replay.
    """

    phase_name: ClassVar[str] = "post-review"

    key: str = ""
    artifact_score: dict = field(default_factory=dict)
    per_document_scores: dict | None = None
    present_to_user: str = ""
    status: str = "UNKNOWN"
    actionable_findings: int = 0
    forward_phase: str = ""
    forward_cmd: str = ""
    other_phase: str | None = None
    other_cmd: str | None = None
    pending_instr: str = ""
    clear_instr: str = ""
    lifecycle_flags: str = ""
    required_tool_calls: list = field(default_factory=list)
    todo_write_payload: dict | None = None
    post_fix_user_choices: list = field(default_factory=list)
    post_fix_user_choices_excluded: list = field(default_factory=list)
    # Literal headline rendered by the gate at post-review time. The
    # next launch reads this off the snapshot and substitutes it into
    # the sub-agent prompt template — the agent echoes a literal
    # instead of recomputing the status from its own observations.
    # Defaults to "" so legacy snapshots without the field round-trip.
    gate_score_headline: str = ""


@dataclass(frozen=True)
class PostFixSnapshot(PhaseSnapshotBase):
    """Snapshot persisted by the ``post-fix`` phase.

    The TODO namespace is ``owned_todo_ids`` (launched from
    :mod:`review_quality.todo_lifecycle`) — post-fix does not carry a
    separate list.
    """

    phase_name: ClassVar[str] = "post-fix"

    key: str = ""
    updated_counts: dict = field(default_factory=dict)
    quality_artifact_refreshed: bool = False
    artifact_score: dict | None = None
    re_review_required: bool = False
    fix_cycle: int = 0
    max_cycles: int = 0
    can_continue: bool = True
    next_action: str = ""
    prompt_command: str = ""
    post_fix_user_choices_excluded: list = field(default_factory=list)
    forward_phase: str = ""
    forward_cmd: str = ""
    other_phase: str | None = None
    other_cmd: str | None = None
    pending_instr: str = ""
    clear_instr: str = ""
    lifecycle_flags: str = ""
    required_tool_calls: list = field(default_factory=list)
    todo_write_payload: dict | None = None


@dataclass(frozen=True)
class CheckRevalidationSnapshot(PhaseSnapshotBase):
    """Snapshot persisted by the ``check-revalidation`` phase.

    Currently not replayed at runtime — check-revalidation always
    recomputes from the doc mtime — but the typed shape exists so
    future callers can opt in without touching the untyped flat-dict
    pathway.
    """

    phase_name: ClassVar[str] = "check-revalidation"

    key: str = ""
    re_review_required: bool = False
    fix_cycle: int = 0
    max_cycles: int = 0
    can_continue: bool = True
    next_action: str = ""
    next_action_command: str = ""
    prompt_command: str = ""
    post_fix_user_choices_excluded: list = field(default_factory=list)
    reason: str = ""


_SUBCLASSES: dict[str, type[PhaseSnapshotBase]] = {
    cls.phase_name: cls
    for cls in (
        PostReviewSnapshot,
        PostFixSnapshot,
        CheckRevalidationSnapshot,
    )
}


def snapshot_cls_for(phase_name: str) -> type[PhaseSnapshotBase] | None:
    """Return the :class:`PhaseSnapshotBase` subclass for ``phase_name``.

    ``None`` when the phase has no typed snapshot — callers fall back
    to the raw dict shape on the session (untyped replay path).
    """
    return _SUBCLASSES.get(phase_name)
