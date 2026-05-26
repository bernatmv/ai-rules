# Three-Pass Task Validation

## Contents
- [Source of Truth](#source-of-truth)
- [Pass 1: Validate Existing Tasks](#pass-1-validate-existing-tasks)
- [Pass 2: Gap Analysis](#pass-2-gap-analysis)
- [Pass 3: Build Updated Task List](#pass-3-build-updated-task-list)
- [Critical Rules](#critical-rules)

Algorithm for regenerating tasks.md from an updated design.md while preserving completed work.

## Source of Truth

The **design.md** is the source of truth for what tasks should exist. The current **tasks.md** represents the implementation state. The goal is to reconcile the two.

### Input

- `design.md` — the approved (potentially updated) design document
- `tasks.md` — the current task list with completion markers
- `Implementation Logs/` — records of completed task implementations

### Output

- Updated `tasks.md` with completed tasks preserved, pending tasks aligned to design, and new tasks added

---

## Pass 1: Validate Existing Tasks

For each task in the current `tasks.md`:

### Completed tasks `[x]`

1. Read the task's corresponding implementation log
2. Verify the task's scope still exists in design.md (the design section it implements)
3. **Action**: ALWAYS preserve completed tasks — never remove or modify them
4. If the design section was removed or significantly changed:
   - Flag the task with a note: `<!-- Design section modified — completed work preserved -->`
   - Surface this to the user in the diff summary

### In-progress tasks `[-]`

1. Check if the task's design section still exists
2. **Action**: Warn user and ask:
   - "Preserve as-is and continue?" → keep `[-]`
   - "Reset to pending?" → change to `[ ]` and update description
   - "Remove?" → add to removal list

### Pending tasks `[ ]`

1. Check if the task's design section still exists and is unchanged
2. **Unchanged**: Keep the task as-is
3. **Modified**: Update the task description, `_Prompt`, `_Leverage`, `_Requirements` to match new design
4. **Removed from design**: Add to removal list

---

## Pass 2: Gap Analysis

Identify design sections that have no corresponding task.

### Process

1. Extract all implementable sections from design.md:
   - API endpoints defined but not yet tasked
   - Components described but not yet tasked
   - Data models defined but not yet tasked
   - Integration patterns described but not yet tasked
2. Cross-reference against existing tasks (including completed ones)
3. For each gap, create a new task entry

### Gap Classification

| Gap Type | Action |
|----------|--------|
| New design section | Create new task |
| Expanded existing section | Extend existing task or create subtask |
| New integration requirement | Create integration task |
| New test requirement | Create test task |

---

## Pass 3: Build Updated Task List

Assemble the final tasks.md:

### Ordering Rules

1. Completed tasks `[x]` — retain original position and numbering
2. Validated pending tasks `[ ]` — retain position, update content if needed
3. New tasks — append after existing tasks with sequential numbering
4. Removed tasks — excluded from output, listed in removal summary

### Numbering

- Preserve existing task IDs for completed and validated tasks
- Assign new sequential IDs for new tasks (continuing from the highest existing ID)
- Never reuse a task ID that was previously completed

### _Prompt Generation for New Tasks

Each new task must include a `_Prompt` field with:
- Role: specialized developer role
- Task: clear description referencing design.md sections
- Restrictions: constraints from design.md
- _Leverage: files/utilities from design.md and completed tasks
- _Requirements: requirement IDs from requirements.md
- Success: specific completion criteria

---

## Critical Rules

| Rule | Rationale |
|------|-----------|
| Never delete completed `[x]` tasks | Implementation work is verified and logged |
| Never renumber completed task IDs | Implementation logs reference task IDs |
| Always flag design-removed completed tasks | User awareness of potential orphaned code |
| New tasks must reference design.md sections | Traceability |
| Present diff before writing | User must approve changes |
| In-progress tasks need explicit user decision | Cannot safely assume intent |
