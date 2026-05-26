# Harness Notes

> **Related protocols:** Read by SKILL bodies that consume
> `pipeline-tick`-rendered envelopes (`required_tool_calls`,
> `next_action_command`).
> Used by: every cross-harness payload consumer.
> See also: `harness-detection.md` (identity resolution),
> `prompt-conventions.md` § Integration Pattern.

Pipeline payload consumers on non-Cursor harnesses: use this reference
to understand the cross-harness shape of ``required_tool_calls`` and
other adapter-rendered envelopes.

For how identity is resolved, see
[`harness-detection.md`](harness-detection.md).

## Contents

- [TODO tool variants](#todo-tool-variants)
- [AskQuestion / AskUserQuestion prompts](#askquestion--askuserquestion-prompts)
- [Sub-agent dispatch](#sub-agent-dispatch)

## TODO tool variants

Every pipeline phase emits one ``required_tool_calls[]`` entry with
``tool: "TodoWrite"`` and ``args.todos: [...]``. The adapter shapes
``args.todos`` for the active host; auditor hints on the envelope
disambiguate which surface the payload targets:

- ``harness_name`` — e.g. ``cursor`` /
  ``claude-code-task-variant``.
- ``harness_tool`` — ``TodoWrite`` on Cursor and standard Claude Code,
  ``TaskUpdate`` on the Task variant.

**Task variant specifics.** Under the Claude Code Task variant,
symbolic pipeline IDs (``step3``, ``fix-c1-apply``, ``approve``) appear
as ``[id] …`` prefixes in ``description``. The runtime assigns a
numeric ID; the symbolic one is recovery metadata only. That means a
reader cross-referencing pipeline logs can still find
``[fix-c1-apply]`` in the task description even though the runtime's
internal ID may be ``#14``.

**No-TODO hosts.** If the active adapter exposes neither ``TodoWrite``
nor ``TaskUpdate`` in ``deferred_tools()`` (and the host is not Cursor,
which exposes ``TodoWrite`` eagerly), the envelope **must** emit the
``required_tool_calls[TodoWrite]`` entry at ``severity: skip`` with a
reason pointing at ``--phase ack-calls``. Consumers that render
``required_tool_calls`` as user instructions MUST hide
``severity: skip`` entries — the pipeline's TODO bookkeeping is closed
out via ``ack-calls`` alone. :meth:`review.actions.Action.todo_write`
enforces this contract.

## AskQuestion / AskUserQuestion prompts

Prompt rendering is handled by ``sdd_core.prompts.render_prompt`` (used
by ``util/generate-prompt.py``). The Cursor adapter emits the
``{id, prompt, options, allow_multiple}`` shape; the Claude Code
adapters emit ``{question, header, multiSelect, options:
[{label, description}]}``. ``header`` truncation is applied at render
time so downstream payloads never exceed the 12-character host limit.

## Sub-agent dispatch

``HarnessAdapter.dispatch_hints()`` tells the parent which tool to use
when launching a review sub-agent:

- Cursor → ``Task(subagent_type=...)``.
- Claude Code (both variants) → ``Task`` (no ``subagent_type``
  argument).

The review pipeline's ``sub_agent_prompt`` is harness-agnostic —
dispatch hints only affect *how* the parent invokes the sub-agent
tool, not the body it passes in.
