"""Shared adapter building blocks.

Cursor owns the ``TodoWrite`` shape; Claude Code (standard + task
variant) share the ``TaskCreate`` / ``TaskUpdate`` shape. The two
mixins below are the single source for each payload so concrete
adapters only override the pieces their host actually differs on
(capabilities string, dispatch hints).
"""
from __future__ import annotations

from .adapter import PipelineTodo, SelfcheckResult

__all__ = ["_TodoListMixin", "_TaskListMixin"]


class _SelfcheckMixin:
    """Shared ``todo.tool`` selfcheck used by both TODO-style mixins."""

    def selfcheck(self) -> list[SelfcheckResult]:
        try:
            payload = self.build_todo_payload([])  # type: ignore[attr-defined]
            return [
                SelfcheckResult(
                    "todo.tool",
                    isinstance(payload, list),
                    "empty todo list renders",
                )
            ]
        except Exception as exc:  # pragma: no cover — defensive
            return [SelfcheckResult("todo.tool", False, str(exc))]


class _TodoListMixin(_SelfcheckMixin):
    """``TodoWrite``-style rendering (Cursor)."""

    def build_todo_payload(self, todos: list[PipelineTodo]) -> list[dict]:
        return [
            {
                "id": t.id,
                "content": t.description,
                "status": t.status,
            }
            for t in todos
        ]


class _TaskListMixin(_SelfcheckMixin):
    """``TaskCreate`` / ``TaskUpdate`` rendering for Claude Code hosts.

    The symbolic pipeline id is prepended as ``[prefix]`` inside the
    description so it remains visible after the host auto-assigns its
    own numeric id. ``kind`` selects between ``TaskCreate`` (new
    entries) and ``TaskUpdate`` (existing entries whose status moved
    beyond ``pending``).
    """

    def build_todo_payload(self, todos: list[PipelineTodo]) -> list[dict]:
        return [
            {
                "kind": "TaskUpdate" if t.status != "pending" else "TaskCreate",
                "id_hint": t.id,
                "description": f"[{t.id}] {t.description}",
                "status": t.status,
            }
            for t in todos
        ]
