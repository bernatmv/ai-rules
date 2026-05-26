"""Claude Code (standard) harness adapter.

Standard Claude Code exposes ``TaskCreate`` / ``TaskUpdate`` (deferred)
for TODO tracking and ``AskUserQuestion`` (header ≤12 chars, per-option
``description``). ``Task`` / ``Agent`` launches do not accept
``subagent_type``.
"""
from __future__ import annotations

from typing import Literal, Mapping

from .adapter import (
    HarnessAdapter,
    PromptSpec,
    SubAgentDispatchHints,
)
from .adapters_common import _TaskListMixin

__all__ = ["ClaudeCodeStandardAdapter"]

# Claude Code caps ``header`` at this many display columns; payloads
# that exceed it are truncated silently at render time on the host
# side, so we truncate here for deterministic behaviour.
_MAX_HEADER_LEN = 12


def _truncate_header(raw: str, fallback_id: str) -> str:
    header = (raw or fallback_id.replace("-", " ").title()).strip()
    if len(header) > _MAX_HEADER_LEN:
        return header[:_MAX_HEADER_LEN].rstrip()
    return header


class ClaudeCodeStandardAdapter(_TaskListMixin):
    """Adapter for the default Claude Code surface."""

    name = "claude-code-standard"

    def build_prompt_payload(self, spec: PromptSpec) -> dict:
        return {
            "questions": [
                {
                    "question": spec.prompt,
                    "header": _truncate_header(spec.header, spec.id),
                    "multiSelect": spec.multi_select,
                    "options": [
                        {
                            "label": opt.label,
                            "description": opt.description or opt.label,
                        }
                        for opt in spec.options
                    ],
                }
            ],
        }

    def dispatch_hints(self) -> SubAgentDispatchHints:
        return SubAgentDispatchHints(
            tool_name="Task",
            subagent_type_supported=False,
        )

    def todo_tool_name(self) -> str:
        return "TaskUpdate"

    def build_residue_reconcile_call(self) -> dict | None:
        # Approval-delete has no authoritative view of which pipeline
        # task IDs are still open on the Claude Code host — task state
        # flows through the host's TaskCreate/TaskUpdate surface out of
        # band from this script. Downgrade to ``severity: skip`` so
        # renderers hide the entry and the host's own reconciliation
        # via ``ack-calls`` remains the single authority.
        return {
            "tool": "TaskUpdate",
            "severity": "skip",
            "reason": (
                "No pipeline-tracked tasks available to reconcile from "
                "approval/delete.py. Agent-owned tasks remain the agent's "
                "responsibility."
            ),
        }

    def capabilities(self) -> Mapping[str, object]:
        hints = self.dispatch_hints()
        return {
            "todo.tool": self.todo_tool_name(),
            "prompt.schema": "claude-code-askuserquestion",
            "sub_agent.dispatch": hints.tool_name,
            "sub_agent.subagent_type": hints.subagent_type_supported,
        }

    def prompt_default_format(self) -> Literal["harness", "markdown"]:
        return "markdown"

    def deferred_tools(self) -> tuple[str, ...]:
        return ("AskUserQuestion", "TaskCreate", "TaskUpdate", "WebFetch")


_DEFAULT = ClaudeCodeStandardAdapter()


def default_instance() -> HarnessAdapter:
    return _DEFAULT
