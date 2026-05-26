# Fix Loop Protocol

Fix-then-re-review cycle shared by all review types. Referenced by:
- `sdd-review-code/SKILL.md` (Step 7)
- `sdd-implement-spec/SKILL.md` (Step 8d)
- `review-approval-pipeline.md` § Fix-Loop State Machine

## Contents

- [State Machine](#state-machine)
- [Fix-Loop Parameters](#fix-loop-parameters)
- [Root Cause Kinds](#root-cause-kinds)
- [Deferring to External Workflow](#deferring-to-external-workflow)
- [TODO Lifecycle](#todo-lifecycle)
- [Caller Bindings](#caller-bindings)
- [Mandatory Execution Checklist](#mandatory-execution-checklist)
- [Code Review Specifics](#code-review-specifics)

## State Machine

Single-source state machine for all fix-then-re-review cycles.

```
Initialize: fix_cycle = 0

PRESENT → present {fix_prompt} via AskQuestion:
  fix_all / fix_selected / fix_critical → FIX → fix_cycle++ → RE_VALIDATE
  skip / proceed                        → DONE(NEEDS_WORK)
  rerun_review [if rerun_option]        → RE_REVIEW (no cycle increment)

RE_VALIDATE → execute each step in validate_steps:
  Any step fails → DONE(NEEDS_WORK, detail from failed step)
  All pass       → RE_REVIEW

RE_REVIEW →
  fix_cycle >= max_cycles → MAX_CYCLES_EXHAUSTED
  fix_cycle < max_cycles  →
    Present `fix-loop-continue` prompt (MANDATORY)
    Execute review per review_mode → findings?
      No  → DONE(PASS)
      Yes → PRESENT

MAX_CYCLES_EXHAUSTED →
  pre-approval accepts with warning
  User may reject approval if last-cycle fixes were significant

Terminal states:
  DONE(PASS)              — all issues resolved
  DONE(NEEDS_WORK)        — outstanding issues, report reason
  MAX_CYCLES_EXHAUSTED    — proceeded to approval with stale-doc warning
```

## Fix-Loop Parameters

| Param | Type | Description |
|-------|------|-------------|
| `fix_prompt` | string | Registry prompt key for the fix decision |
| `validate_steps` | list | Ordered validation commands |
| `review_mode` | `inline` or `sub_agent` | How to execute re-review |
| `max_cycles` | int | Max fix→re-review loops (default: 2) |
| `rerun_option` | bool | Whether the prompt includes a "re-run review" option |

## Root Cause Kinds

Every actionable Tier-2 finding written by a sub-agent must declare a
`root_cause_kind` from the canonical enum. The post-review aggregator
branches on the kind mix to choose the recommended `--user-choice`.

| Kind | When it applies |
|------|-----------------|
| `in_doc` | Fix lives entirely in the doc(s) under review. Default kind. Routes through `fix_all`. |
| `external_state` | Blocking artifact lives outside this doc — missing steering files, unrun migrations, undeployed dependency. Cannot be cleared by editing the doc. Routes through `defer_to_external_workflow`. |
| `cross_doc` | Contradiction between sibling docs in the same spec (e.g. requirements.md says X, design.md says Y). Fixing one doc requires editing another. Routes through `fix_all` with the cross-doc edit explicit. |
| `criteria_dispute` | The facet's pass criteria are themselves the wrong test for this doc — raise with the human reviewer rather than the doc author. Routes through `fix_all` with a flag for human escalation. |

Schema enforcement: `update-quality.py --input` rejects any tier2-score
finding (or `cross_validation.pairs[*].findings[*]` of type `conflict`)
that lacks `root_cause_kind`. Legacy artifacts written before the
requirement landed default to `in_doc` at READ time so existing
fixtures continue to route through `fix_all`.

Aggregator → recommendation:

| Kind mix | `user_choice_recommended` | Extra envelope fields |
|----------|---------------------------|-----------------------|
| All `in_doc` | (legacy default — `fix_all`) | none |
| All `external_state` | `defer_to_external_workflow` | `defer_remediation_command` |
| Mixed (in_doc + external/cross/criteria) | `fix_all_in_doc_first` | `deferred_findings_hint` (and `defer_remediation_command` when external_state present) |

## Deferring to External Workflow

When every actionable finding roots outside the doc, fixing in-band
cannot clear the gate. The post-review envelope surfaces:

- `user_choice_recommended: "defer_to_external_workflow"`
- `defer_remediation_command: "<runnable command>"` — e.g. `Run /sdd-create-steering then resume the review gate.`

Choosing `--user-choice defer_to_external_workflow` at the next
post-fix invocation:

1. Refreshes line counts on the artifact.
2. Appends a `phase_history` entry with `phase: "defer_external"`,
   `user_choice: "defer_to_external_workflow"`, `fix_cycle`, and
   `recorded_at` so a later session sees the deferral as an immutable
   row alongside approve / reject events.
3. Advances the gate to `pre-approval` WITHOUT incrementing
   `fix_cycle` — the budget carries forward so a follow-up in-band
   fix loop after the external workflow runs is not penalised.

The defer choice is suppressed on envelopes whose findings include no
`external_state` row, and on transitions where `findings_count == 0`.

## TODO Lifecycle

All `prepare-pipeline.py` phases return `todo_write_payload` when `--parent-todo`
is provided. Callers MUST pass this payload directly to TodoWrite after each phase
call. Do NOT reshape keys — the payload is the exact TodoWrite argument.

Example payload from phase output:
```json
{"todo_write_payload": {"todos": [{"id": "step3", "content": "...", "status": "in_progress"}, {"id": "fix-c1-apply", "content": "...", "status": "in_progress"}], "merge": true}}
```
→ `TodoWrite(todos=todo_write_payload.todos, merge=true)`

See `review_quality/todo_lifecycle.py` for the event model and TODO encoding.
Do NOT manually compute TODO transitions — the script handles all state logic.

**Owned-ID rule:** Do NOT manually create fix-loop cycle TODOs (IDs matching `fix-c{N}-*`). These are managed exclusively by pipeline phases via `todo_write_payload`. The agent's only responsibility is to pass `todo_write_payload` to TodoWrite after each phase call. Pre-creating these TODOs causes duplicate visual groups in the IDE. Pipeline output includes `owned_todo_ids` — never `TodoWrite` those IDs independently.

### TODO Encoding

Example for cycle 1:

- id: `fix-c1-apply`    → "Fix loop cycle 1: apply fixes"
- id: `fix-c1-validate` → "Fix loop cycle 1: validate changes"
- id: `fix-c1-review`   → "Fix loop cycle 1: re-review ({scope})"

The validate and review TODOs act as gates — they cannot be marked complete
without actually performing the verification and re-review.

## Caller Bindings

| Caller | `fix_prompt` | `validate_steps` | `review_mode` | `rerun_option` | `max_cycles` |
|--------|-------------|-------------------|---------------|----------------|-------------|
| Code review (standalone) | `fix-action` | 1. `git diff --stat` | `inline` | `false` | 2 |
| Code review (impl sub-agent) | `fix-action` | 1. `git diff --stat` | `sub_agent` | `false` | 2 |
| Code review (remote PR) | `fix-action-readonly` | (none — read-only) | `inline` | `false` | 0 |
| Document review (gate) | `review-fix-issues` | 1. `pre-approval-validation.md`  2. `check-re-review.py` | `sub_agent` | `true` | `max_fix_cycles` param |

**Note:** `max_fix_cycles` controls fix iterations only. It does NOT bypass the stale-doc re-review redirect in `pre-approval` (see `review-approval-pipeline.md § Review Gate Protocol Steps` — Step 5 Edit invariant). When max cycles are exhausted with stale docs, `pre_approval` blocks unless the user has explicitly accepted via `user_accepted_at`.

Caller-specific details (prompt templates, validation commands, review scoping
rules) remain in the caller file:
- Code review: This file § Code Review Specifics
- Document review: `review-approval-pipeline.md` § Review Gate Protocol Steps

## Mandatory Execution Checklist

See `review-approval-pipeline.md` § Review Gate Checklist Fragment for the
document review variant.

## Code Review Specifics

### Prompt Structure

Generate the `fix-action` prompt via `.spec-workflow/sdd util/generate-prompt.py --type fix-action`.
See `prompt-conventions.md` § Integration Pattern.

Substitute these params:
- `critical_count`: number of Critical findings
- `warning_count`: number of Warning findings
- `suggestion_count`: number of Suggestion findings
- `total_count`: total findings
- `top_findings`: formatted top 3 findings (numbered list)

### Prompt Validation

All fields are required. Do NOT modify:
- Title format: "Code Review — {n} issues found"
- Question id: `fix_action`
- Severity vocabulary: Critical / Warning / Suggestion (from `review-conventions.md`)
- Option ids: `fix_all`, `fix_critical`, `skip`
- Prompt must include severity counts AND top 3 findings

### Validation Behavior

The code review binding uses `git diff --stat` as its validation step:
- No changes → NEEDS_WORK ("Fix attempt produced no changes")
- Changes exist → proceed to RE_REVIEW

### Re-Review Scope

Only re-evaluate:
- Dimensions that had findings in the previous cycle
- Conventions dimension (cheap, catches regressions from fixes)

Do NOT re-evaluate dimensions that passed cleanly.

### Caller Modes

| Caller | Review execution | Fix execution |
|--------|-----------------|---------------|
| `sdd-review-code` (standalone) | Inline — re-run review steps (scoped per § Re-Review Scope) | Agent fixes in current context |
| `sdd-implement-spec` (sub-agent) | Re-launch review sub-agent | Parent agent fixes, then re-invokes sub-agent |
