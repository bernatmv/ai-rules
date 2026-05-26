"""Typed-action entry builders for pipeline envelopes.

Single factory — :class:`Action` — that every phase module uses to
assemble ``required_tool_calls[]`` entries. Each emitted entry
carries:

* ``kind`` — a closed :class:`~review.schema.ActionKind` value.
* ``severity`` — one of :class:`~review.schema.Severity`. Recovery is
  just another severity, not a parallel ``recovery_actions[]`` list.
* ``reason`` — short operator-facing justification.
* ``tool`` / ``args`` — wire shape kept stable for agent clients that
  dispatch on ``tool`` rather than ``kind``.

Downstream adapters read ``args.command`` as the single source of
truth for the shell equivalent of :kind:`PipelineTick` /
:kind:`ShellProbe` actions.

Kept deliberately narrow: every kind has its own concrete factory
method so the wire shape is documented in code rather than via
free-form ``payload`` dicts. New kinds arrive as new methods.
"""
from __future__ import annotations

from typing import Any

from .schema import ActionKind, Severity

__all__ = ["Action"]


# Wire ``tool`` value for shell-equivalent dispatch (PipelineTick / ShellProbe);
# legacy clients dispatch on this rather than ``kind``.
TOOL_SHELL = "Shell"
# Wire ``tool`` value for sub-agent dispatch entries; mirrors :kind:`Task`.
TOOL_TASK = "Task"
# Wire ``tool`` value for declarative informational prompts (:kind:`Instruction`).
TOOL_INSTRUCTION = "Instruction"
# Wire ``tool`` value for declarative user-question prompts (:kind:`AskQuestion`).
TOOL_ASK_QUESTION = "AskQuestion"


def _severity_value(severity: "str | Severity") -> str:
    """Return the wire string for ``severity``.

    Accepts either a :class:`Severity` enum member or its string value
    so callers can pass ``"info"`` directly without importing the enum.
    Rejects unknown values loudly: phase modules must pick from the
    closed vocabulary, not fabricate new severities.
    """
    if isinstance(severity, Severity):
        return severity.value
    value = str(severity)
    if value not in {s.value for s in Severity}:
        raise ValueError(
            f"Unknown severity '{value}'. "
            f"Expected one of: {[s.value for s in Severity]}"
        )
    return value


def _kind_value(kind: "str | ActionKind") -> str:
    """Return the wire string for ``kind``.

    Enum-or-string symmetry mirrors :func:`_severity_value`. Keeps
    phase modules decoupled from the :class:`ActionKind` import while
    still funnelling every action through the closed vocabulary.
    """
    if isinstance(kind, ActionKind):
        return kind.value
    value = str(kind)
    if value not in {k.value for k in ActionKind}:
        raise ValueError(
            f"Unknown action kind '{value}'. "
            f"Expected one of: {[k.value for k in ActionKind]}"
        )
    return value


class Action:
    """Namespaced factories for typed ``required_tool_calls[]`` entries.

    Every method returns a plain :class:`dict` (not a dataclass) so
    the value can be appended to ``result['required_tool_calls']``
    without a subsequent serialisation step. Consumers that read
    ``tool``/``args`` keep working untouched; consumers that read
    ``kind`` first fall back to ``tool``/``args`` only when ``kind``
    is absent.
    """

    # Concrete factory per kind ------------------------------------------------

    @staticmethod
    def todo_write(
        payload: dict,
        *,
        reason: str = "",
        severity: "str | Severity" = Severity.INFO,
    ) -> dict[str, Any]:
        """Build a :kind:`TodoWrite` entry.

        Consult the active harness adapter so ``args.todos`` is shaped
        for the current host: Cursor receives the ``TodoWrite`` list
        shape, Claude Code (standard / task-variant) hosts receive
        ``TaskCreate`` / ``TaskUpdate`` envelopes. ``harness_tool`` /
        ``harness_name`` carry the auditor hints consumers read; the
        legacy ``tool`` field mirrors ``harness_tool`` so the wire
        shape never carries two contradictory tool names.
        """
        entry: dict[str, Any] = {
            "kind": _kind_value(ActionKind.TODO_WRITE),
            "severity": _severity_value(severity),
            "reason": reason,
            "args": payload,
        }
        # Deferred import keeps the dependency edge lazy (``review.actions``
        # is loaded from inside ``sdd_core`` during module import).
        from sdd_core.harness import load_adapter
        from sdd_core.harness.adapter import PipelineTodo

        todos = payload.get("todos") if isinstance(payload, dict) else None
        if not isinstance(todos, list):
            return entry
        typed_todos = []
        for t in todos:
            if not isinstance(t, dict):
                continue
            typed_todos.append(
                PipelineTodo(
                    id=str(t.get("id", "")),
                    description=str(t.get("content") or t.get("description") or ""),
                    status=t.get("status", "pending"),
                )
            )
        from sdd_core.harness.detectors import HarnessContradictionError
        try:
            adapter = load_adapter()
            rendered = adapter.build_todo_payload(typed_todos)
        except HarnessContradictionError:
            return entry
        todo_tool = adapter.todo_tool_name()
        if not todo_tool:
            # Adapters that genuinely cannot host any TODO surface
            # downgrade to ``severity: skip`` and route the agent to
            # ``--phase ack-calls``. Renderers MUST hide skipped entries.
            entry["severity"] = _severity_value(Severity.SKIP)
            entry["reason"] = (
                "Active harness exposes no TODO surface — pipeline TODO "
                "state is ack-tracked via --phase ack-calls only."
            )
            entry["harness_name"] = adapter.name
            return entry
        rendered_args: dict[str, Any] = dict(payload) if isinstance(
            payload, dict,
        ) else {}
        rendered_args["todos"] = rendered
        entry["args"] = rendered_args
        entry["harness_tool"] = todo_tool
        entry["harness_name"] = adapter.name
        # ``tool`` mirrors ``harness_tool`` so legacy consumers reading
        # ``entry.get("tool")`` see the resolved harness surface (e.g.
        # ``TaskUpdate`` on Claude Code standard) instead of a hardcoded
        # ``"TodoWrite"`` that contradicts ``harness_tool``.
        entry["tool"] = todo_tool
        return entry

    @staticmethod
    def pipeline_tick(
        *,
        event: str,
        command: str,
        gate_id: str = "",
        reason: str = "",
        severity: "str | Severity" = Severity.INFO,
    ) -> dict[str, Any]:
        """Build a :kind:`PipelineTick` entry.

        ``command`` is the equivalent ``Shell`` invocation an older
        agent client can dispatch directly; ``event`` + ``gate_id``
        are the declarative fields a typed-action adapter reads
        first. ``args.command`` is the authoritative shell string —
        no ``render_as`` mirror.
        """
        return {
            "kind": _kind_value(ActionKind.PIPELINE_TICK),
            "severity": _severity_value(severity),
            "reason": reason,
            "event": event,
            "gate_id": gate_id,
            "tool": TOOL_SHELL,
            "args": {"command": command},
        }

    @staticmethod
    def ask_question(
        *,
        prompt_type: str,
        params: dict[str, Any] | None = None,
        reason: str = "",
        severity: "str | Severity" = Severity.INFO,
    ) -> dict[str, Any]:
        """Build an :kind:`AskQuestion` entry.

        Pure declarative: the envelope carries ``prompt_type`` +
        ``params`` only, and the adapter invokes
        :func:`sdd_core.prompts.render_prompt` at execution time. No
        ``rendered`` payload accompanies the declarative shape —
        two representations of the same prompt on the wire is the
        drift pattern we avoid.
        """
        return {
            "kind": _kind_value(ActionKind.ASK_QUESTION),
            "severity": _severity_value(severity),
            "reason": reason,
            "prompt_type": prompt_type,
            "params": dict(params or {}),
            "tool": TOOL_ASK_QUESTION,
            "args": {"prompt_type": prompt_type, "params": dict(params or {})},
        }

    @staticmethod
    def instruction(
        *,
        prompt_type: str,
        params: dict[str, Any] | None = None,
        reason: str = "",
        severity: "str | Severity" = Severity.INFO,
    ) -> dict[str, Any]:
        """Build an :kind:`Instruction` entry.

        Mirrors :meth:`ask_question` but renders one of the
        ``pipeline-instruction-*`` prompt types — informational
        guidance that is not itself a user-facing question.
        """
        return {
            "kind": _kind_value(ActionKind.INSTRUCTION),
            "severity": _severity_value(severity),
            "reason": reason,
            "prompt_type": prompt_type,
            "params": dict(params or {}),
            "tool": TOOL_INSTRUCTION,
            "args": {"prompt_type": prompt_type, "params": dict(params or {})},
        }

    @staticmethod
    def task(
        payload: dict,
        *,
        reason: str = "",
        severity: "str | Severity" = Severity.INFO,
    ) -> dict[str, Any]:
        """Build a :kind:`Task` entry (sub-agent dispatch).

        ``payload`` is opaque at this layer — the sub-agent echo
        contract is enforced server-side and only the payload shape
        needs to reach the adapter.
        """
        return {
            "kind": _kind_value(ActionKind.TASK),
            "severity": _severity_value(severity),
            "reason": reason,
            "tool": TOOL_TASK,
            "args": payload,
        }

    @staticmethod
    def shell_probe(
        command: str,
        *,
        reason: str = "",
        severity: "str | Severity" = Severity.INFO,
    ) -> dict[str, Any]:
        """Build a :kind:`ShellProbe` entry.

        Reserved for genuinely-external commands (e.g. ``git``,
        ``find``, ``docker``) that are not pipeline verbs. Pipeline
        dispatches should prefer :meth:`pipeline_tick` so the
        lifecycle flags resolve server-side. ``args.command`` is the
        authoritative shell string.
        """
        return {
            "kind": _kind_value(ActionKind.SHELL_PROBE),
            "severity": _severity_value(severity),
            "reason": reason,
            "tool": TOOL_SHELL,
            "args": {"command": command},
        }

    # Generic dispatcher -------------------------------------------------------

    @staticmethod
    def build(
        kind: "str | ActionKind",
        **fields: Any,
    ) -> dict[str, Any]:
        """Dispatch to the concrete factory for ``kind``.

        Call sites that already know the kind at authoring time should
        prefer the concrete method (``Action.todo_write(...)``) because
        kwargs are validated by each method's signature. This dispatcher
        exists for the rare consumer (tests, lints, replay tooling)
        that has ``kind`` as runtime data.
        """
        value = _kind_value(kind)
        factory = _FACTORIES.get(value)
        if factory is None:  # pragma: no cover - defensive
            raise ValueError(f"No factory registered for kind '{value}'")
        return factory(**fields)


_FACTORIES: dict[str, Any] = {
    ActionKind.TODO_WRITE.value: Action.todo_write,
    ActionKind.PIPELINE_TICK.value: Action.pipeline_tick,
    ActionKind.ASK_QUESTION.value: Action.ask_question,
    ActionKind.INSTRUCTION.value: Action.instruction,
    ActionKind.TASK.value: Action.task,
    ActionKind.SHELL_PROBE.value: Action.shell_probe,
}
