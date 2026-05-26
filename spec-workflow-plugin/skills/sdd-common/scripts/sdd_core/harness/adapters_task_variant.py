"""Claude Code Task-variant harness adapter.

Preserved as a distinct harness name for detection (hosts that advertise
the Task-variant marker explicitly route here) even though the Task-style
TODO payload is now shared with the standard Claude Code adapter via
:class:`_TaskListMixin`. The capability string uses the combined
``TaskCreate/TaskUpdate`` label so legacy consumers that parsed the
wire-name continue to see the task-variant branding.
"""
from __future__ import annotations

from typing import Mapping

from .adapter import HarnessAdapter
from .adapters_claude_code import ClaudeCodeStandardAdapter

__all__ = ["ClaudeCodeTaskVariantAdapter"]


class ClaudeCodeTaskVariantAdapter(ClaudeCodeStandardAdapter):
    """Adapter for Claude Code hosts that advertise the Task-variant marker."""

    name = "claude-code-task-variant"

    def capabilities(self) -> Mapping[str, object]:
        hints = self.dispatch_hints()
        return {
            "todo.tool": "TaskCreate/TaskUpdate",
            "prompt.schema": "claude-code-askuserquestion",
            "sub_agent.dispatch": hints.tool_name,
            "sub_agent.subagent_type": hints.subagent_type_supported,
        }


_DEFAULT = ClaudeCodeTaskVariantAdapter()


def default_instance() -> HarnessAdapter:
    return _DEFAULT
