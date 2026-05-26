---
name: sdd-implement-spec
description: Implements approved spec tasks through a systematic execution loop with
  implementation logging and artifact tracking. Use when asked to implement a spec,
  resume implementation, implement next task, continue implementing, or log a task.
allowed-tools: Read Write Edit Bash Agent AskQuestion AskUserQuestion TaskCreate TaskUpdate WebFetch
metadata:
  version: 3.3.1
  category: development
  dependencies: [sdd-common]
  author: membership-platforms-sdd-guild
---

> **Paths:** See `$SKILLS/sdd-common/references/path-conventions.md`. Scripts: `.spec-workflow/sdd {group}/{script}.py`.

# SDD: Implement Spec

Implements approved spec tasks through a systematic execution loop: check prerequisites, load context, execute tasks one-by-one with implementation logging and artifact tracking.

## Contents

- [Dependencies](#dependencies)
- [Invocation Examples](#invocation-examples)
- [Workflow](#workflow)
- [Resumption Guidance](#resumption-guidance)
- [Workflow Progress](#workflow-progress)
- [Safety Rules](#safety-rules)
- [Edge Cases](#edge-cases)
- [Completion](#completion)
- [Reference Files](#reference-files)

## Dependencies

> Load each file only when the workflow reaches that step. Freedom legend: see `$SKILLS/sdd-common/references/freedom-column.md`.

| Step | File | Kind | Freedom |
|------|------|------|:-:|
| Step 1 | `$SKILLS/sdd-common/references/tool-patterns.md` | read | L |
| Step 1 | `$SKILLS/sdd-common/scripts/spec/check-status.py` | run | L |
| Step 4 | `$SKILLS/sdd-implement-spec/references/task-execution-loop.md` | read | M |
| Step 5 | `$SKILLS/sdd-implement-spec/references/implementation-rules.md` | read | H |
| Step 5 | `$SKILLS/sdd-common/references/telemetry.md` | read | L |
| Step 5 | `$SKILLS/sdd-common/scripts/util/log-implementation.py` | run | L |
| Step 5 (artifacts) | `$SKILLS/sdd-implement-spec/references/artifact-schema.md` | read | L |
| Step 5 (artifacts) | `$SKILLS/sdd-implement-spec/references/artifact-examples.md` | read | M |
| Step 4, 6 | `$SKILLS/sdd-common/scripts/impl/advance-task.py` | run | L |
| Step 4 (multi-file) | `$SKILLS/sdd-common/scripts/impl/plan-task.py` | run | L |
| Step 4 (multi-file) | `$SKILLS/sdd-common/scripts/impl/validate-plan.py` | run | L |
| Step 8 | `$SKILLS/sdd-common/references/review-approval-pipeline.md` (§ Sub-Agent Guidelines, § Fix-Loop) | read | L |
| Step 8 | `$SKILLS/sdd-common/references/fix-loop-protocol.md` | read | L |
| Resume | `$SKILLS/sdd-implement-spec/references/impl-session-schema.md` | read | L |
| All | `$SKILLS/sdd-common/references/state-scope.md` (scope + lifetime of persisted state) | read | L |

## Invocation Examples

| Request | Action |
|---------|--------|
| "sdd implement [name]" | Start or resume implementation |
| "sdd implement next [name]" | Execute next pending task |
| "sdd log task [name] [task-id]" | Log a completed task |

## Workflow

### Step 1: Check Prerequisites

Verify the spec is ready for implementation.

```
.spec-workflow/sdd spec/check-status.py --spec-name "{spec-name}"
```

| Check | Required | Action on Failure |
|-------|----------|-------------------|
| requirements.md exists | Yes | "Spec not ready. Create requirements first." |
| requirements.md approved | Yes | "Requirements need approval: `sdd approve spec {name}`" |
| design.md exists | Yes | "Spec not ready. Create design first." |
| design.md approved | Yes | "Design needs approval: `sdd approve spec {name}`" |
| tasks.md exists | Yes | "Spec not ready. Create tasks first." |
| tasks.md approved | Yes | "Tasks need approval: `sdd approve spec {name}`" |

If any check fails, report what's missing and suggest the appropriate action. Do NOT proceed with implementation until all three documents are approved.

### Step 2: Load Context

Read all spec documents to understand the full scope:

1. Read `.spec-workflow/specs/{spec-name}/requirements.md`
2. Read `.spec-workflow/specs/{spec-name}/ui-design.md` if it exists (for UI/UX context)
3. Read `.spec-workflow/specs/{spec-name}/design.md`
4. Read `.spec-workflow/specs/{spec-name}/tasks.md`
5. **MUST** read `.spec-workflow/steering/tech.md` and `structure.md` if they exist — they contain architecture constraints that apply to all tasks.

### Step 3: Select Task

Parse `tasks.md` and determine which task to execute:

| Priority | Condition |
|----------|-----------|
| 1st | Any task marked `[-]` (in_progress) — resume it |
| 2nd | First task marked `[ ]` (pending) — start it |
| None | All tasks `[x]` — implementation complete |

Present the selected task to the user with its `_Prompt` field, `_Leverage` references, and `_Requirements` traceability.

> **Verification-only determination:** Run `check-pre-existing.py --batch-check` for the full task list:
> ```bash
> .spec-workflow/sdd util/check-pre-existing.py --spec-name "{spec-name}" --batch-check
> ```
> If `all_pre_existing: true`:
> 1. Announce: "Verification-only spec — executing sequential per-task logging."
> 2. For each task, still follow the full Step 4 → 5 → 6 loop (abbreviated presentation, but sequential logging via `advance-task.py`).
> 3. Set `--statistics '{"preExisting": true}'` in all logs.
>
> If `all_pre_existing: false`:
> - Check `non_pre_existing` array for the specific tasks.
> - Log the pre-existing tasks sequentially (abbreviated presentation, `preExisting: true`).
> - Execute non-pre-existing tasks individually with full `_Prompt`, `_Leverage`, and `_Requirements` presentation.

### Step 4: Execute Task

Follow `references/task-execution-loop.md` for the per-task procedure (Steps 4a–4g checklist).

> **Multi-file tasks (>5 files):** Before any edits, emit and validate an
> `edit-plan.json` to declare scope up-front.
>
> ```bash
> .spec-workflow/sdd impl/plan-task.py --spec-name "{name}" --task-id "{id}" \
>   --file path/to/file.py:modify --out /tmp/edit-plan.json
> .spec-workflow/sdd impl/validate-plan.py /tmp/edit-plan.json
> ```
>
> Thresholds (file count, size-delta cap) live in
> `references/implementation-rules.md`. Apply the validated plan, then
> resume the normal logging flow in Step 5.

### Step 5: Log Implementation

**MANDATORY**: Log before marking the task complete.

> See `$SKILLS/sdd-common/references/telemetry.md` § Log the Implementation for the canonical invocation, argument formats, and artifact requirements.

See `references/artifact-schema.md` for the full schema and `references/artifact-examples.md` for good/bad examples.

A task without an implementation log is NOT complete. Do NOT change `[-]` to `[x]` until the log succeeds.

### Step 6: Mark Complete

Only after `log-implementation.py` returns success — see `references/task-execution-loop.md` Step 4g for the exact command and error recovery.

### Step 7: Loop or Complete

- If more tasks remain: return to Step 3 (select next task)
- If all tasks are `[x]`: proceed to Step 8 (post-implementation review)

### Step 8: Post-Implementation Code Review

All tasks complete. Offer a code review before finalizing.

> **Verification-only skip:** If `.impl-session.json` shows `execution_mode: "verification-only"` and all tasks logged with `preExisting: true`, code review is not applicable (no files changed). Skip to Step 9 with message: "All tasks were pre-existing verifications. Code review skipped."

**8a: Present review offer**

Use AskQuestion to offer the code review:

| Option | Action |
|--------|--------|
| Run code review now | Continue to Step 8b |
| Skip review | Go to Step 9 (completion) |

**8b: Launch review sub-agent**

Launch a Task sub-agent for `sdd-review-code`:

Run the code-review launch command emitted on the implementation envelope's `template_resolve_commands.code_review_launch_md` field (canonical builder: `sdd_core.command_templates.build_pipeline_tick_code_review_launch_command`).

The script returns a `next_action_command` with the sub-agent prompt. Execute it.

On any blocked/pending-calls response, follow `$SKILLS/sdd-common/references/review-approval-pipeline.md` § Pending Tool Calls Enforcement (covers `required_tool_calls` ordering and `next_action_sequence` recovery).

Sub-agent parameters:
- `mode`: `spec-aware`
- `target_name`: `{spec-name}`
- `target_path`: `{project_path}`
- `review_skill_path`: `$SKILLS/sdd-review-code/SKILL.md`

The sub-agent returns a structured result (defined in the template's Return
contract): overall score, per-dimension results, findings list, positives.

**8c: Present review summary**

Format the sub-agent return per its contract:
- Overall score and status (PASS / NEEDS WORK / FAIL)
- Per-dimension scorecard
- Issue count by severity
- Top 5 findings

**8d: Fix loop**

Follow `$SKILLS/sdd-common/references/fix-loop-protocol.md` with caller
mode = sub-agent. Execute its **Mandatory Execution Checklist** step by step.

**Hard constraints:**
- RE-VALIDATE and RE-REVIEW are mandatory after applying fixes.
- Do NOT report review results without executing the full checklist.

### Step 9: Complete

Report implementation and review status. The next step is typically `sdd-review-code` for a code-quality review; archival is optional via `sdd archive {spec-name}` once the spec is fully complete.

## Resumption Guidance

When resuming implementation (user says "sdd implement [name]" for an existing spec):

1. Read `.impl-session.json` for richer context recovery:
   - If session exists: use `execution_mode`, `completed_tasks`, and `current_task` to determine resume point.
   - If session absent: fall back to `check-status.py --verify-logs`.
2. Run `.spec-workflow/sdd spec/check-status.py --spec-name "{name}" --verify-logs`
3. If `logVerification.missingLogs` is non-empty:
   - Present to user: "Tasks {ids} are marked complete but have no implementation logs."
   - Reset those tasks to `[ ]` in tasks.md.
   - Resume from the first reset task.
4. If `overallStatus` is `"completed"` and `logVerification.verified` is true: proceed to Step 8.
5. If in-progress or pending tasks remain: select next task per Step 3.
6. Search existing implementation logs for context:
   ```
   rg "taskId" ".spec-workflow/specs/{spec-name}/Implementation Logs/"
   ```

## Workflow Progress

Copy this checklist and track progress:

```
- [ ] Step 1: Check prerequisites (all docs approved) — Triage: T0
- [ ] Step 2: Load context (read all spec docs)
- [ ] Step 3: Select task (if batch determination fails, explain why)
- [ ] Step 4: Execute task
- [ ] Step 5: Log implementation
- [ ] Step 6: Mark complete
- [ ] Step 7: Loop or proceed to review
- [ ] Step 8: Post-Implementation Code Review
  - → AskQuestion: "Run code review?" (opt-in review)
  - → If review: sub-agent runs sdd-review-code (spec-aware mode)
  - → If issues: AskQuestion fix loop per fix-loop-protocol.md (max 2 cycles)
- [ ] Step 9: Complete
```

## Safety Rules

See `$SKILLS/sdd-common/references/safety-rules.md`. Key rules for this skill: All docs must be approved before implementation; log before marking complete; search logs before implementing.

## Edge Cases

See `$SKILLS/sdd-common/references/common-edge-cases.md` for shared patterns (Spec Not Found, Resume Existing). Skill-specific edge cases:

| Situation | Action |
|-----------|--------|
| Docs not approved | Report which docs need approval, suggest action |
| Task already in-progress | Resume it instead of starting a new one |
| Implementation log fails | Retry; do NOT mark task complete |
| All tasks complete | Proceed to Step 8 (post-implementation review) |
| Sub-agent review fails / times out | Report failure to user, skip to Step 9. Do NOT block completion. Suggested timeout: 5 minutes. If the sub-agent is unresponsive after 5 min, kill and retry once. On second failure, skip review. |
| Fix loop introduces new test failures | Stop fixing, present failures to user, proceed to Step 9 with NEEDS WORK status. |
| User skips review | Record skip in implementation summary, proceed to Step 9. |
| Task has no _Prompt field | Warn user, implement based on task description |
| Conflicting implementation logs | Surface conflict to user, ask for guidance |
| Test failures | Consult `references/troubleshooting.md` before escalating. Present `test-failure` prompt from registry via AskQuestion |

Invocation for the `test-failure` prompt:

```
.spec-workflow/sdd util/generate-prompt.py --type test-failure
```

## Completion

Implementation complete. The next step is typically `sdd-review-code` for a code-quality review; archival is optional via `sdd archive {spec-name}` once the spec is fully complete.

## Reference Files

- Task execution loop: references/task-execution-loop.md
- Implementation rules: references/implementation-rules.md
- Artifact schema: references/artifact-schema.md
- Artifact examples: references/artifact-examples.md
- Implementation session schema: references/impl-session-schema.md
- Troubleshooting: references/troubleshooting.md
- Task validation rules: $SKILLS/sdd-common/references/task-validation-rules.md
- Script conventions: $SKILLS/sdd-common/references/script-conventions.md
- Sub-agent guidelines: $SKILLS/sdd-common/references/review-approval-pipeline.md § Sub-Agent Guidelines
- Fix loop protocol: $SKILLS/sdd-common/references/fix-loop-protocol.md
