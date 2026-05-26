---
name: sdd-manage-status
description: Manages spec status checks, approval transitions, and task regeneration.
  Use when asked to check spec status, show spec progress, approve a spec, approve
  steering, reject a spec, request revision, list pending approvals, refresh tasks,
  regenerate tasks, or sync tasks from design.
allowed-tools: Read Write Edit Bash Agent AskQuestion AskUserQuestion TaskCreate TaskUpdate WebFetch
metadata:
  version: 3.3.1
  category: workflow
  dependencies: [sdd-common]
  author: membership-platforms-sdd-guild
---

> **Paths:** See `$SKILLS/sdd-common/references/path-conventions.md`. Scripts: `.spec-workflow/sdd {group}/{script}.py`.

# SDD: Manage Status

Three operational modes:

| Mode | Purpose | Triggers |
|------|---------|----------|
| **Status Check** | Display spec phases, task progress, and approval states | "status", "check status", "show progress", "spec status" |
| **Approval Management** | Transition approval status with audit logging | "approve", "reject", "request revision", "list pending" |
| **Task Refresh** | Regenerate tasks.md from updated design.md | "refresh tasks", "regenerate tasks", "sync tasks", "update tasks from design" |

## Contents

- [Dependencies](#dependencies)
- [Mode Detection (Invocation Examples)](#mode-detection)
- [Actor Detection](#actor-detection)
- [Status Check](#status-check)
- [Approval Management](#approval-management)
- [Task Refresh](#task-refresh)
- [Workflow Progress](#workflow-progress)
- [Safety Rules](#safety-rules)
- [Edge Cases](#edge-cases)
- [Completion](#completion)
- [Reference Files](#reference-files)

## Dependencies

> Load each file only when the workflow reaches that step. Freedom legend: see `$SKILLS/sdd-common/references/freedom-column.md`.

| Step | File | Kind | Freedom |
|------|------|------|:-:|
| Steps S1/R1 | `$SKILLS/sdd-common/references/tool-patterns.md` | read | L |
| Steps S1/R1 | `$SKILLS/sdd-common/scripts/spec/check-status.py` | run | L |
| Step A1 | `$SKILLS/sdd-common/scripts/approval/list-pending.py` | run | L |
| Steps A2/A3 | `$SKILLS/sdd-common/references/prompt-conventions.md` | read | L |
| Steps A2/A3 | `$SKILLS/sdd-common/scripts/util/generate-prompt.py` (prompt access) | run | L |
| Step A4 | `$SKILLS/sdd-common/scripts/approval/update-status.py` | run | L |
| Step R4 | `$SKILLS/sdd-manage-status/references/three-pass-validation.md` | read | M |
| Step R5 | `$SKILLS/sdd-manage-status/references/migration-patterns.md` | read | M |
| Step R10 | `$SKILLS/sdd-common/scripts/approval/request.py` | run | L |
| All | `$SKILLS/sdd-common/references/approval-flow.md` | read | L |
| Step R4 | `$SKILLS/sdd-common/references/task-validation-rules.md` | read | M |
| Conditional | `$SKILLS/sdd-common/references/detection-rules.md` (spec type detection) | read | M |
| Edge cases | `$SKILLS/sdd-manage-status/references/troubleshooting.md` | read | M |
| Edge cases | `$SKILLS/sdd-manage-status/references/audit-log-schema.md` | read | L |
| Edge cases | `$SKILLS/sdd-common/references/common-edge-cases.md` | read | M |
| All | `$SKILLS/sdd-common/references/state-scope.md` (scope + lifetime of persisted state) | read | L |

## Mode Detection

| User Request | Mode |
|-------------|------|
| "sdd status [name]" | Status Check |
| "sdd status" | Status Check |
| "sdd approve spec [name]" | Approval |
| "sdd approve steering" | Approval |
| "sdd reject [name] [doc]" | Approval |
| "sdd request revision [name]" | Approval |
| "sdd list pending" | Approval |
| "sdd refresh tasks [name]" | Task Refresh |

## Actor Detection

Determine the `actor` field dynamically for audit logging:
- If running in **Cursor** (detected by `.cursor/` skill path or Cursor-specific config): `"cursor-agent"`
- If running in **Claude Code** (detected by `.claude/` skill path or Claude-specific context): `"claude-code-agent"`
- Fallback: `"unknown-agent"`

## Status Check

Read-only mode that displays spec phases, task progress, approval states, and suggests next actions.

### Step S1: Check Status

```
# Single spec
.spec-workflow/sdd spec/check-status.py --spec-name "{spec-name}"

# All specs
.spec-workflow/sdd spec/check-status.py --all
```

### Step S2: Present Results

Display a status summary table for each spec:

```markdown
## Spec: {spec-name}

| Phase | Status | Details |
|-------|--------|---------|
| requirements.md | {approved/created/missing} | {summary} |
| design.md | {approved/created/missing} | {summary} |
| tasks.md | {approved/created/missing} | {summary} |
| Implementation | {not-started/in_progress/complete} | {x}/{total} tasks |

**Pending approvals**: {count}
**Implementation logs**: {count} entries
```

For task-level detail, parse `tasks.md` and show:

```markdown
### Tasks

| ID | Status | Description |
|----|--------|-------------|
| 1 | [ ] Pending | {description} |
| 2 | [-] In progress | {description} |
| 3 | [x] Complete | {description} |
```

### Step S3: Suggest Next Steps

| Current Phase | Suggested Action |
|---------------|-----------------|
| No spec exists | "Create a spec: `sdd create spec {name}`" |
| requirements.md missing | "Start spec creation: `sdd create spec {name}`" |
| requirements.md created (not approved) | "Approve requirements: `sdd approve spec {name}`" |
| requirements.md approved, design.md missing | "Resume spec creation: `sdd resume spec {name}`" |
| design.md created (not approved) | "Approve design: `sdd approve spec {name}`" |
| design.md approved, tasks.md missing | "Resume spec creation: `sdd resume spec {name}`" |
| tasks.md created (not approved) | "Approve tasks: `sdd approve spec {name}`" |
| All approved, no tasks started | "Start implementation: `sdd implement {name}`" |
| Tasks in progress | "Continue implementation: `sdd implement {name}`" |
| All tasks complete | "Spec complete! Archive with: `sdd archive {name}`" |

## Approval Management

### Step A1: Discover Pending Approvals

```
.spec-workflow/sdd approval/list-pending.py [--category spec|steering] [--spec-name "{spec-name}"]
```

Exit 0 → JSON array of pending items; proceed to Step A2.
Exit 1 → No pending approvals; report and stop.

For targeted requests (e.g., "approve spec user-auth"), add `--spec-name user-auth`.
Extract the `_source_file` field from each result for Step A4.

### Step A2: Present Pending Approvals

When multiple pending approvals exist, present the `approval-formal` prompt from the registry via AskQuestion with per-approval options:

```
.spec-workflow/sdd util/generate-prompt.py --type approval-formal --params doc=<value>
```

Display before taking action:

```markdown
| # | Document | Spec/Category | Approval ID | Requested At |
|---|----------|---------------|-------------|--------------|
| 1 | requirements.md | spec/user-auth | approval_xxx | 2026-02-22 |
| 2 | design.md | spec/user-auth | approval_yyy | 2026-02-22 |
```

### Step A3: Confirm Intent

**NEVER change status without explicit user confirmation.**

Follow `$SKILLS/sdd-common/references/approval-flow.md` § Pattern B.

For targeted requests where user already specified the action (e.g., "approve spec user-auth"), skip the selection step and proceed directly.

**Follow-up for `approve_custom` / `needs_revision`:** Prompt "Please enter a comment:" and read the user's next chat message as the `response` text. See `$SKILLS/sdd-common/references/prompt-conventions.md` § Free-Text Collection.

**Dry-run support**: If user says "dry-run", show preview without writing.

**Non-pending override:** If status is not `pending`:

Present the `approval-override` prompt from the registry with params
`current_status={status}`:

```
.spec-workflow/sdd util/generate-prompt.py --type approval-override --params current_status=<value>
```

See `$SKILLS/sdd-common/references/prompt-conventions.md` § Integration Pattern.

If override selected, collect reason via free-text prompt. Stored as `response` with `type: "approval-status-override"` in audit log.

### Step A4: Execute Status Change

```
.spec-workflow/sdd approval/update-status.py "{_source_file}" "{action}" "{response}" --actor "{actor}"
```

Exit 0 → status updated, audit log entry appended to `.spec-workflow/approval-audit.log`.
Non-zero → error; do not proceed.

**Transition rule**: Only `pending` → `approved` / `rejected` / `needs_revision`. Other transitions require explicit user override with extra confirmation.

### Step A5: Write Audit Log

The `approval/update-status.py` script atomically:
1. Validates pending status
2. Updates JSON fields (`status`, `response`, `respondedAt`)
3. Writes back pretty-printed
4. Appends JSONL audit entry to `.spec-workflow/approval-audit.log`
5. Verifies the write

### Step A6: Report Results

```markdown
## Status Change Results

| Document | Spec/Category | Action | Result |
|----------|---------------|--------|--------|
| requirements.md | spec/user-auth | approved | Success |

Audit log updated: `.spec-workflow/approval-audit.log`
```

Inform user they can proceed to the next phase. The workflow agent handles cleanup (e.g., `approval/delete.py`) — this mode does not call delete.

Approval complete. To start implementation, run `sdd implement {spec-name}`.

## Task Refresh

Regenerates tasks.md from updated design.md, preserving completed work.
See `references/task-refresh-workflow.md` for the full procedure (Steps R1–R10).

Key safety rules:
- Preserve all completed `[x]` tasks exactly
- Warn before modifying in-progress `[-]` tasks
- Never write without user confirmation (Step R8)

## Workflow Progress

Copy the relevant checklist for the active mode and track progress:

### Status Check

```
- [ ] Step S1: Check status — Triage: T0
- [ ] Step S2: Present results
- [ ] Step S3: Suggest next steps
```

### Approval Management

```
- [ ] Step A1: Discover pending approvals — Triage: T0
- [ ] Step A2: Present approval list
- [ ] Step A3: Confirm action with user — Triage: T0/T1
- [ ] Step A4: Execute status change
- [ ] Step A5: Write audit log
- [ ] Step A6: Report results
```

### Task Refresh

```
- [ ] Step R1: Validate prerequisites
- [ ] Step R2: Read current state
- [ ] Step R3: Identify completed tasks
- [ ] Step R4: Three-pass validation
- [ ] Step R5: Handle migration patterns
- [ ] Step R6: Generate updated tasks.md
- [ ] Step R7: Present diff to user
- [ ] Step R8: Confirm with user
- [ ] Step R9: Write updated tasks.md
- [ ] Step R10: Request approval
```

## Safety Rules

See `$SKILLS/sdd-common/references/safety-rules.md`. Key rules for this skill: Never auto-approve in a loop; require response text for all transitions; only transition from `pending` unless user override.

## Edge Cases

See `$SKILLS/sdd-common/references/common-edge-cases.md` for shared patterns (Approval Rejected, Spec Not Found). Skill-specific edge cases:

| Situation | Action |
|-----------|--------|
| Corrupt tasks.md | Report parsing error, suggest manual inspection |
| Spec in archive | Check `.spec-workflow/archive/` and report if found there |
| Steering docs requested | Also check `.spec-workflow/steering/` and report doc status |
| Multiple specs | Show summary table for all, then detail for requested spec |
| No pending approvals | Report "No pending approvals found" and stop |
| Multiple approvals for same doc | Present all, let user choose |
| Task refresh with no design changes | Report "No changes detected" and skip |
| Task refresh with in-progress tasks | Present `task-in-progress` prompt from registry via AskQuestion |
| Completed tasks reference deleted design sections | Preserve tasks but flag for review |
| Migration pattern detected | Apply progressive migration from migration-patterns.md |
| User requests non-pending transition | Present `approval-override` prompt from registry via AskQuestion |

Invocations for the edge-case prompts above:

```
.spec-workflow/sdd util/generate-prompt.py --type task-in-progress
```

```
.spec-workflow/sdd util/generate-prompt.py --type approval-override --params current_status=<value>
```

## Completion

Status operation complete.

## Reference Files

- Three-pass validation: references/three-pass-validation.md
- Migration patterns: references/migration-patterns.md
- Approval flow: $SKILLS/sdd-common/references/approval-flow.md
- Task validation rules: $SKILLS/sdd-common/references/task-validation-rules.md
- Detection rules: $SKILLS/sdd-common/references/detection-rules.md
- Troubleshooting: references/troubleshooting.md
- Audit log schema: references/audit-log-schema.md
