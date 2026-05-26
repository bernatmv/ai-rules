# Task Refresh Workflow

Regenerates `tasks.md` from an updated `design.md` using three-pass validation to preserve completed work and add new tasks.

## Steps R1–R10

### Step R1: Validate Prerequisites

```
.spec-workflow/sdd spec/check-status.py --spec-name "{spec-name}"
```

Require: design.md exists and is approved. tasks.md exists. If tasks.md doesn't exist, redirect to `sdd-create-spec` for initial task creation.

### Step R2: Read Current State

1. Read `.spec-workflow/specs/{spec-name}/design.md` (source of truth)
2. Read `.spec-workflow/specs/{spec-name}/tasks.md` (current tasks)
3. Read implementation logs: `.spec-workflow/specs/{spec-name}/Implementation Logs/`

### Step R3: Identify Completed Tasks

Parse tasks.md for markers:
- `[x]` = completed — these tasks are preserved as-is
- `[-]` = in_progress — warn user:

Present the `task-in-progress` prompt from the registry with params:
`task_id={task-id}`. See `$SKILLS/sdd-common/references/prompt-conventions.md` § Integration Pattern.

- `[ ]` = pending — these may be updated, replaced, or removed

### Step R4: Three-Pass Validation

Follow `three-pass-validation.md`:

**Pass 1 — Validate Existing**: Check each current task still aligns with design.md
**Pass 2 — Gap Analysis**: Identify design sections with no corresponding task
**Pass 3 — Build Updated List**: Merge validated tasks + new tasks

### Step R5: Handle Migration Patterns

If design changes involve technology or architecture migrations, follow `migration-patterns.md` for progressive migration task structures.

### Step R6: Generate Updated tasks.md

Build the new tasks.md:
1. Completed tasks `[x]` — preserved exactly (including implementation log references)
2. Validated pending tasks `[ ]` — updated descriptions if needed
3. New tasks from gap analysis — added with proper `_Prompt`, `_Leverage`, `_Requirements`
4. Removed tasks — listed in a removal summary

### Step R7: Present Diff to User

Show a comparison:

```markdown
## Task Refresh Summary

| Action | Count | Tasks |
|--------|-------|-------|
| Preserved (completed) | {n} | {task IDs} |
| Updated (pending) | {n} | {task IDs} |
| Added (new) | {n} | {task IDs} |
| Removed | {n} | {task IDs} |
```

### Step R8: Confirm with User

Present the full updated tasks.md for review. **NEVER write without user confirmation.**

Present the `task-refresh-confirm` prompt from the registry via AskQuestion.
See `$SKILLS/sdd-common/references/prompt-conventions.md` § Integration Pattern.

### Step R9: Write Updated tasks.md

Write the updated tasks.md to `.spec-workflow/specs/{spec-name}/tasks.md`.

### Step R10: Request Approval

The refreshed tasks.md needs re-approval:

```
.spec-workflow/sdd approval/request.py --target-name "{spec-name}" \
  --title "Tasks (refreshed): {spec-name}" \
  --file-paths ".spec-workflow/specs/{spec-name}/tasks.md" \
  --type document --category spec
```

Follow `$SKILLS/sdd-common/references/approval-flow.md` § Pattern A for the approval cycle. 3-cycle iteration limit.
