# Harness Task Binding

> Used by: pipeline phases that emit ``required_tool_calls[]``,
> sub-agent adapters that consume the symbolic ``id_hint``.
> See also: `harness-notes.md` (cross-harness shape overview),
> `harness-detection.md` (identity resolution),
> `review-approval-pipeline.md` § Fix-Loop.

The pipeline correlates every TODO it emits with its tick-recorded
completion record by a **symbolic identifier** (``id_hint``), not by
the host's auto-assigned numeric task id. This page documents the
contract so adapters and pipeline phases stay aligned.

## Contents

- [Pipeline emission contract](#pipeline-emission-contract)
- [Harness adapter mapping](#harness-adapter-mapping)
- [Reconciliation](#reconciliation)
- [Typed wire shape — RequiredToolCallsPayload](#typed-wire-shape--requiredtoolcallspayload)
  - [`consumer` field](#consumer-field)
  - [`lifecycle_mirror` naming](#lifecycle_mirror-naming)
- [Why symbolic ids](#why-symbolic-ids)

## Pipeline emission contract

A ``required_tool_calls`` entry of ``kind: "TodoWriteEquivalent"``
carries ``args.todos: [...]`` where each row has:

- ``id_hint`` — symbolic, non-empty, stable across emit/reconcile
  cycles (``step3``, ``fix-c1-apply``, ``approve``).
- ``description`` — human-readable summary the operator sees.
- ``status`` — one of ``pending`` / ``in_progress`` / ``completed``.
- ``parent_id_hint`` — optional symbolic link to a parent ``id_hint``.

Empty ``id_hint`` is forbidden by contract — pipeline reconciliation
correlates emitted TODOs with their tick-recorded completion records
by symbolic id, and an empty value silently breaks that linkage.
Construction sites that flow through :class:`sdd_core.harness.adapter.PipelineTodo`
have the invariant enforced at the boundary; phases that build the
``args.todos[]`` rows directly are expected to validate before append.

## Harness adapter mapping

Adapters translate the contract into the host's TODO surface:

- **Cursor / standard Claude Code** (``TodoWrite``):
  ``{"id": id_hint, "content": description, "status": status}``.
- **Claude Code task variant** (``TaskCreate`` / ``TaskUpdate``):
  ``{"kind": "TaskCreate"|"TaskUpdate", "id_hint": id_hint,
  "description": "[id_hint] description", "status": status}``.
  The bracketed id_hint is preserved in the description so the
  symbolic identifier survives the host's auto-numbered ids.

The ``harness_tool`` field on the payload (``TodoWrite`` /
``TaskCreate`` / ``TaskUpdate`` / ``TaskComplete``) names the
host's actual TODO surface; ``harness_name`` is the adapter id.

## Reconciliation

``pipeline-tick.py`` reconciles emitted TODOs against the
gate-session record using ``id_hint`` exclusively. Description-
substring matching is forbidden — the description is operator-
facing display only and may drift between emit and complete.

When the host invokes ``TaskUpdate(id=<numeric>, ...)``, the
adapter echoes the original ``id_hint`` back via the next
``pipeline-tick`` payload so the pipeline sees the symbolic id
on every cycle.

## Typed wire shape — RequiredToolCallsPayload

`sdd_core.required_tool_calls.RequiredToolCallsPayload` is the
single-owner constructor for the wire shape above. New emit sites
build through the dataclass so the legacy `tool: "TodoWrite"` field
is structurally absent.

### `consumer` field

`consumer` names who runs the payload — the routing decision lives
on the wire instead of being inferred at the harness adapter:

- `consumer: "harness_adapter"` — pipeline-owned ids subject to
  `displaces_todo_id_hints`. The adapter mirrors the lifecycle to
  the host's task surface (TaskCreate / TaskUpdate on Claude Code;
  TodoWrite on Cursor).
- `consumer: "agent"` — agent-authored ids the agent must update
  directly. The adapter does not reconcile.

### `lifecycle_mirror` naming

Field name `lifecycle_mirror` (not `todos`) makes the role explicit
on the wire — the entries are *mirror* rows the adapter reconciles
against the host's task/todo surface, not abstract items the agent
writes back. Existing callers continue to use `args.todos` until
their migration window opens — both shapes pass the regression guard
in `tests/test_review/pipeline_phases/test_recurrence_guards.py`.

## Why symbolic ids

Numeric ids belong to the host. The pipeline lives across hosts
and across runs (resumption, replay, parallel batches). Encoding
pipeline semantics in the host's auto-assigned ids would couple
the two — every host change would force a pipeline rewrite. The
symbolic ``id_hint`` carries pipeline-side semantics (gate ids,
fix-cycle markers, reference reads) that the host never has to
understand.
