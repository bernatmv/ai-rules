"""Harness-adapter interface + domain dataclasses.

The pipeline speaks a harness-agnostic dialect: ``PipelineTodo`` for
workflow progress tracking, ``PromptSpec`` for user-facing prompts, and
``SubAgentDispatchHints`` for Task-style launches. Every adapter
translates those domain objects into the shape its host expects.
Adapter methods return plain dicts / lists / strings so callers can
``json.dumps`` the payload directly; ``selfcheck`` is consulted by
``util/probe-harness.py`` before ``harness.json`` is written.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping, Protocol, runtime_checkable

__all__ = [
    "PipelineTodo",
    "PromptOption",
    "PromptSpec",
    "SelfcheckResult",
    "SubAgentDispatchHints",
    "HarnessAdapter",
    "TodoStatus",
]


# Canonical status vocabulary for :class:`PipelineTodo`. Adapters map
# these onto their host's native status enum (Cursor/Claude Code:
# ``pending`` / ``in_progress`` / ``completed``; Task variant shares the
# same tokens today).
TodoStatus = Literal["pending", "in_progress", "completed"]


@dataclass(frozen=True)
class PipelineTodo:
    """Pipeline-emitted TODO entry (harness-agnostic).

    ``id`` is the symbolic pipeline identifier (``step3``,
    ``fix-c1-apply``, ``approve``). Non-empty by contract — empty
    ``id_hint`` is forbidden because pipeline reconciliation relies
    on the symbolic id to correlate the emitted TODO with its
    tick-recorded completion. Adapters may need to tunnel the symbolic
    id through alternate-shaped APIs — the Task-variant adapter
    prepends ``[id]`` to the description because ``TaskCreate``
    auto-assigns numeric IDs.
    """

    id: str
    description: str
    status: TodoStatus

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError(
                "PipelineTodo.id is required: empty symbolic ids "
                "break pipeline reconciliation. Pass a unique id_hint "
                "for every emitted TODO."
            )


@dataclass(frozen=True)
class PromptOption:
    """A single option on a :class:`PromptSpec`.

    ``id`` is the stable machine-readable key (Cursor needs it).
    ``label`` is the short display string both Cursor and Claude Code
    render. ``description`` is the long-form blurb shown alongside the
    label on Claude Code's ``AskUserQuestion``.
    """

    id: str
    label: str
    description: str = ""


@dataclass(frozen=True)
class PromptSpec:
    """Host-agnostic prompt spec.

    Carries every field any supported harness might need (schema
    superset). Each adapter's :meth:`HarnessAdapter.build_prompt_payload`
    picks the subset its host consumes.
    """

    id: str
    prompt: str
    options: tuple[PromptOption, ...]
    title: str = ""
    header: str = ""
    multi_select: bool = False


@dataclass(frozen=True)
class SubAgentDispatchHints:
    """Per-harness hints for launching review sub-agents.

    * ``tool_name`` — the agent-facing tool (``Task`` / ``Agent`` / …).
    * ``subagent_type_supported`` — whether the tool accepts a
      ``subagent_type`` argument (Cursor does; standard Claude Code
      currently does not).
    * ``prompt_arg_name`` — which keyword the tool expects for the
      sub-agent prompt body (``prompt`` everywhere today, kept
      parameterised so a future host with e.g. ``input`` plugs in).
    """

    tool_name: str
    subagent_type_supported: bool
    prompt_arg_name: str = "prompt"


@dataclass(frozen=True)
class SelfcheckResult:
    """One entry in the :meth:`HarnessAdapter.selfcheck` report.

    ``passed`` gates whether ``util/probe-harness.py`` is willing to
    persist ``harness.json``. ``detail`` is a human-readable explanation
    that shows up on failure.
    """

    capability: str
    passed: bool
    detail: str = ""


@runtime_checkable
class HarnessAdapter(Protocol):
    """Protocol every adapter implements.

    Implementations live in :mod:`sdd_core.harness.adapters_cursor`,
    :mod:`sdd_core.harness.adapters_claude_code`, and
    :mod:`sdd_core.harness.adapters_task_variant`.
    :func:`registry.get_adapter` asserts structural conformance at
    lookup time.
    """

    #: Stable string identifier — matches the key in
    #: :data:`registry.ADAPTERS` and the ``harness`` field written to
    #: ``harness.json``.
    name: str

    def build_todo_payload(self, todos: list[PipelineTodo]) -> list[dict]:
        """Render pipeline todos into the host's TODO-tool argument shape."""
        ...

    def build_prompt_payload(self, spec: PromptSpec) -> dict:
        """Render a prompt into the host's ask-prompt argument shape."""
        ...

    def dispatch_hints(self) -> SubAgentDispatchHints:
        """Return dispatch metadata the parent uses to launch sub-agents."""
        ...

    def selfcheck(self) -> list[SelfcheckResult]:
        """Return a capability-selfcheck report.

        The probe refuses to persist ``harness.json`` if any entry's
        ``passed`` is ``False``. Keep the checks cheap — they run on
        every probe invocation.
        """
        ...

    def capabilities(self) -> Mapping[str, object]:
        """Return the host capability map written into ``harness.json``.

        Concrete adapters expose their own wire names (``todo.tool``,
        ``prompt.schema``, ``sub_agent.dispatch``,
        ``sub_agent.subagent_type``) so the probe does not branch on
        adapter name. Downstream consumers read the map verbatim — no
        central mapping arbitrates it.
        """
        ...

    def prompt_default_format(self) -> Literal["harness", "markdown"]:
        """Return the format ``util/generate-prompt.py`` picks when the
        caller does not supply ``--format``.

        Cursor renders the native ``AskQuestion`` JSON; Claude Code
        variants route through the lettered markdown prompt because
        ``AskUserQuestion`` is deferred-loaded. Every adapter overrides
        this explicitly so a missing implementation surfaces at
        protocol-check time.
        """
        ...

    def deferred_tools(self) -> tuple[str, ...]:
        """Host-native tools listed but not callable until the agent
        loads their schema (Claude Code deferred-tool convention).

        Empty tuple on hosts that load everything eagerly. Owned by the
        adapter so workflow guidance never branches on harness name.
        """
        ...

    def todo_tool_name(self) -> str:
        """Return the agent-facing tool name this adapter routes TODO
        writes through (e.g. ``"TodoWrite"`` for Cursor,
        ``"TaskUpdate"`` for Claude Code). Empty string signals "no
        TODO surface" — callers downgrade the entry to
        ``severity: skip`` in that case.
        """
        ...

    def build_residue_reconcile_call(self) -> dict | None:
        """Return a ``required_tool_calls[]`` entry that clears
        residual TODO / task-list entries at skill-run end, or
        ``None`` when the host has no TODO surface.
        """
        ...
