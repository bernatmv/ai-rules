"""Cursor harness adapter.

Cursor exposes ``TodoWrite`` (caller-supplied string ids, ``merge``
argument), ``AskQuestion`` (id-per-option, optional ``allow_multiple``),
and ``Task(subagent_type=…)`` for review launches.
"""
from __future__ import annotations

from typing import Literal, Mapping

from .adapter import (
    HarnessAdapter,
    PromptSpec,
    SubAgentDispatchHints,
)
from .adapters_common import _TodoListMixin

__all__ = ["CursorAdapter"]


class CursorAdapter(_TodoListMixin):
    """Adapter for the Cursor agent surface."""

    name = "cursor"

    def build_prompt_payload(self, spec: PromptSpec) -> dict:
        payload: dict = {
            "questions": [
                {
                    "id": spec.id,
                    "prompt": spec.prompt,
                    "options": [
                        {"id": opt.id, "label": opt.label}
                        for opt in spec.options
                    ],
                    "allow_multiple": spec.multi_select,
                }
            ],
        }
        if spec.title:
            payload["title"] = spec.title
        return payload

    def dispatch_hints(self) -> SubAgentDispatchHints:
        return SubAgentDispatchHints(
            tool_name="Task",
            subagent_type_supported=True,
        )

    def todo_tool_name(self) -> str:
        return "TodoWrite"

    def build_residue_reconcile_call(self) -> dict | None:
        return {
            "tool": "TodoWrite",
            "args": {"todos": []},
            "reason": "Clear residual in_progress / pending tasks at skill-run end.",
        }

    def capabilities(self) -> Mapping[str, object]:
        hints = self.dispatch_hints()
        return {
            "todo.tool": self.todo_tool_name(),
            "prompt.schema": "cursor-askquestion",
            "sub_agent.dispatch": hints.tool_name,
            "sub_agent.subagent_type": hints.subagent_type_supported,
        }

    def prompt_default_format(self) -> Literal["harness", "markdown"]:
        return "harness"

    def deferred_tools(self) -> tuple[str, ...]:
        return ()


_DEFAULT = CursorAdapter()


def default_instance() -> HarnessAdapter:
    return _DEFAULT
