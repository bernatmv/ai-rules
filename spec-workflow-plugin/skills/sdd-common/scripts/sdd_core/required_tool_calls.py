"""Typed schema for ``required_tool_calls[*]`` payloads.

Today every phase that emits a ``required_tool_calls`` row passes the
payload through :class:`review.actions.Action` — a centralised factory
that returns dicts. The factory works, but it leaves the wire shape
itself implicit: nothing on the dict literal stops a future caller
from re-introducing the legacy ``tool: "TodoWrite"`` + ``args.todos``
combination.

This module promotes the wire shape to a typed dataclass:

- :class:`LifecycleMirrorEntry` — one row inside ``args.lifecycle_mirror``.
- :class:`RequiredToolCallsPayload` — the wire envelope. Carries
  ``consumer`` (``"agent"`` vs ``"harness_adapter"``) so the harness
  adapter can make the routing decision structurally instead of by
  reading flag combinations off the dict.

The dataclass renders a dict via :meth:`RequiredToolCallsPayload.to_dict`
that the lint at :mod:`internal_lints.required_tool_calls_schema` will
later check against existing emit sites. The migration is opt-in:
existing :class:`Action` factory output is *compatible* (the lint
allows it because the payloads keep ``args.todos``) but new emit
sites should construct via :class:`RequiredToolCallsPayload` so the
``tool: "TodoWrite"`` field is *structurally absent* — adding it would
require editing the dataclass.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


__all__ = [
    "CONSUMER_AGENT",
    "CONSUMER_HARNESS_ADAPTER",
    "Consumer",
    "HarnessTool",
    "KIND_TODO_WRITE_EQUIVALENT",
    "LifecycleMirrorEntry",
    "RequiredToolCallsPayload",
]


# Single-string vocabulary for the wire shape so every emit site reads
# from the same names. ``HarnessTool`` and ``Consumer`` re-export the
# Literal for type annotations; the bare-string constants below are the
# values emit sites use when constructing payloads.
HarnessTool = Literal["TaskCreate", "TaskUpdate", "TaskComplete", "TodoWrite"]
Consumer = Literal["agent", "harness_adapter"]

KIND_TODO_WRITE_EQUIVALENT: str = "TodoWriteEquivalent"
"""Sole ``kind`` value carried by ``RequiredToolCallsPayload``.

Named so emit sites read the verb (``KIND_TODO_WRITE_EQUIVALENT``)
instead of restating the literal. The dual-channel regression cannot
recur once existing call sites migrate through this constant.
"""

CONSUMER_AGENT: str = "agent"
"""Routing decision: the agent runs the payload directly (no adapter)."""

CONSUMER_HARNESS_ADAPTER: str = "harness_adapter"
"""Routing decision: the harness adapter mirrors the payload to its
task / todo surface (TaskCreate + TaskUpdate on Claude Code; TodoWrite
on Cursor).
"""


@dataclass(frozen=True)
class LifecycleMirrorEntry:
    """One TODO mirror row carried inside ``args.lifecycle_mirror``.

    ``id_hint`` is the symbolic pipeline identifier (``step4``,
    ``fix-c1-apply``); the harness adapter resolves it to a numeric
    backend id when needed (Claude Code's TaskCreate auto-assigns
    numeric ids; the adapter's id_hint→numeric_id cache binds the two
    so subsequent updates address the right row).

    ``parent_id_hint`` is optional — used for nested TODO trees. Empty
    string is the no-parent sentinel so the dict round-trips through
    JSON without a missing key.
    """

    id_hint: str
    description: str
    status: Literal["pending", "in_progress", "completed"]
    parent_id_hint: str = ""

    _VALID_STATUSES: "frozenset[str]" = frozenset(
        {"pending", "in_progress", "completed"},
    )

    def __post_init__(self) -> None:
        if not self.id_hint:
            raise ValueError(
                "LifecycleMirrorEntry.id_hint is required and must be "
                "non-empty: empty symbolic ids break the pipeline / "
                "harness adapter id_hint → numeric_id mapping."
            )
        if not self.description:
            raise ValueError(
                "LifecycleMirrorEntry.description is required and must "
                "be non-empty: the description is the operator-facing "
                "label for the mirror row."
            )
        if self.status not in self._VALID_STATUSES:
            raise ValueError(
                f"LifecycleMirrorEntry.status must be one of "
                f"{sorted(self._VALID_STATUSES)}; got {self.status!r}. "
                "``Literal[...]`` is type-only — runtime callers from "
                "JSON-deserialised payloads need this guard."
            )

    def to_dict(self) -> dict:
        out = {
            "id_hint": self.id_hint,
            "description": self.description,
            "status": self.status,
        }
        if self.parent_id_hint:
            out["parent_id_hint"] = self.parent_id_hint
        return out


@dataclass(frozen=True)
class RequiredToolCallsPayload:
    """The single wire shape for ``required_tool_calls[*]``.

    ``consumer`` names who runs this payload:

    * ``"harness_adapter"`` — pipeline-owned ids (subject to
      ``displaces_todo_id_hints``); the adapter mirrors the lifecycle
      to the agent's task surface (TaskCreate / TaskUpdate on Claude
      Code; TodoWrite on Cursor).
    * ``"agent"`` — agent-authored ids that the agent must update
      directly; the adapter does not reconcile them.

    The ``tool: "TodoWrite"`` field is **structurally absent** —
    adding one would require editing the dataclass. The dual-channel
    regression cannot recur once existing call sites migrate through
    this constructor.

    Field name ``lifecycle_mirror`` (not ``todos``) makes the role
    explicit on the wire — the entries are *mirror* rows the adapter
    reconciles against the harness's task/todo surface, not abstract
    items the agent writes back.
    """

    kind: Literal["TodoWriteEquivalent"]
    harness_tool: HarnessTool
    harness_name: str
    consumer: Consumer
    lifecycle_mirror: tuple[LifecycleMirrorEntry, ...] = field(
        default_factory=tuple,
    )

    def __post_init__(self) -> None:
        # Referential integrity — every ``parent_id_hint`` must either
        # be empty (no parent) or reference a sibling entry's
        # ``id_hint``. Catches typos and stale forks at construction
        # time so the wire shape carries a self-consistent tree.
        ids = {entry.id_hint for entry in self.lifecycle_mirror}
        for entry in self.lifecycle_mirror:
            if entry.parent_id_hint and entry.parent_id_hint not in ids:
                raise ValueError(
                    f"LifecycleMirrorEntry parent_id_hint="
                    f"{entry.parent_id_hint!r} does not match any "
                    f"sibling id_hint; valid ids: {sorted(ids)}"
                )

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "harness_tool": self.harness_tool,
            "harness_name": self.harness_name,
            "consumer": self.consumer,
            "args": {
                "lifecycle_mirror": [e.to_dict() for e in self.lifecycle_mirror],
            },
        }
