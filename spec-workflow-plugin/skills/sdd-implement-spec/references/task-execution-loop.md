# Task Execution Loop

Per-task procedure for implementing a single task from an approved spec.
This is the inner loop for outer Step 4 (Execute Task) in `sdd-implement-spec/SKILL.md`.

Sub-checklist for the parent SKILL.md "Step 4: Execute Task" item:

- [ ] 4a: Mark in-progress → 4a.1: Check pre-existing (skip to 4f if confirmed)
- [ ] 4b: Search existing logs → 4c: Read _Prompt → 4d: Implement → 4e: Test
- [ ] 4f: Log implementation → 4g: Mark complete

## Contents

- [Pre-Implementation](#pre-implementation) — Steps 4a–4c
- [Implementation](#implementation) — Steps 4d–4e
- [Post-Implementation](#post-implementation) — Steps 4f–4g

## Pre-Implementation

### Step 4a: Mark In-Progress

Run `advance-task.py` to atomically update both `tasks.md` and `.impl-session.json`:

```bash
.spec-workflow/sdd impl/advance-task.py --spec-name "{spec-name}" --task-id "{task-id}" --action start
```

The script enforces:
- No other task is already `[-]` (in-progress)
- The prior task has a `log_id` in the session (prevents batched logging)

**Error recovery:**
1. If the error says another task is in-progress, complete that task first (Steps 4f–4g) and retry.
2. If the error says a prior task lacks a `log_id`, run `log-implementation.py` for it first.
3. After 2 failed attempts, escalate to the user with the error details.

### Step 4a.1: Check for Pre-Existing Implementation

Run the pre-existing check script:

```bash
.spec-workflow/sdd util/check-pre-existing.py --spec-name "{spec-name}" --task-id "{task-id}"
```

Act on the JSON result:
- If `pre_existing: true`: Present to user: "Task {id} appears already implemented — {evidence}. Log as pre-existing, or re-implement?"
  - If confirmed: skip to Step 4f with `"preExisting": true` in `--statistics`. Use `verifications` artifact type (see artifact-schema.md).
- If `pre_existing: false`: proceed to Step 4b (search logs) then Step 4d (implement).

> Do NOT skip this step. Do NOT substitute keyword matching for the script check.

### Step 4b: Search Existing Implementation Logs

Before writing any code, search for related work in implementation logs.

If `.spec-workflow/specs/{spec-name}/Implementation Logs/` does not exist, skip this step.

If all logs in the directory are from the current session, skip the search — context is already available.

```bash
# Search for related endpoints
rg "api|endpoint|route" ".spec-workflow/specs/{spec-name}/Implementation Logs/"

# Search for related components
rg "component|page|view" ".spec-workflow/specs/{spec-name}/Implementation Logs/"

# Search for related functions/classes
rg "function|class|utility" ".spec-workflow/specs/{spec-name}/Implementation Logs/"

# Search for specific terms from the task
rg "specific-term-from-task" ".spec-workflow/specs/{spec-name}/Implementation Logs/"
```

Search 2-3 different terms to discover comprehensively.

> **Efficiency note:** Combining search terms into a single regex (e.g., `rg "term1|term2"`) is acceptable when the logs directory has fewer than 10 files.

### Step 4c: Read _Prompt Field

The `_Prompt` field contains structured implementation guidance:

| Section | Purpose |
|---------|---------|
| **Role** | Specialized developer role for the task |
| **Task** | Clear description with context references |
| **Restrictions** | What NOT to do, constraints to follow |
| **_Leverage** | Files/utilities to use — read these first |
| **_Requirements** | Requirements this task implements — verify coverage |
| **Success** | Specific completion criteria — verify before logging |

## Implementation

### Step 4d: Implement the Code

1. Read all `_Leverage` files to understand existing patterns
2. Follow the task description and `_Prompt` guidance
3. Maintain consistency with existing codebase patterns
4. Reuse existing code discovered in log search (Step 4b)

### Step 4e: Test & Verify

1. Run relevant unit tests
2. Run integration tests if applicable
3. Verify against `Success` criteria in `_Prompt`
4. Check for regressions in related functionality
5. **If tests fail or criteria unmet:**
   - Diagnose the failure
   - Fix the implementation
   - Return to sub-step 1 of this section
   - After 3 failed attempts, escalate to user
6. Only proceed to Step 4f when all tests pass

## Post-Implementation

### Step 4f: Log Implementation

**MANDATORY** — call `log-implementation.py` with full artifact details.

> See `$SKILLS/sdd-common/references/telemetry.md` § Log the Implementation for the canonical invocation, artifact requirements, and field reference.

1. Run `log-implementation.py` with required arguments
2. **If exit code ≠ 0:** Review error message, fix arguments, retry
3. After 3 failed attempts, escalate to user with the error details
4. Only proceed to Step 4g when log succeeds (exit code 0)

### Step 4g: Mark Complete

Only after `log-implementation.py` returns exit code 0:

```bash
.spec-workflow/sdd impl/advance-task.py --spec-name "{spec-name}" --task-id "{task-id}" --action finish --log-id "{log-id}"
```

The script verifies the log file exists on disk before allowing the `[-]` → `[x]` transition.

**Error recovery:**
1. If the error says the log file is not found, verify `log-implementation.py` succeeded and retry with the correct `--log-id`.
2. If the error says the current task doesn't match, check `.impl-session.json` for the actual current task.
3. After 2 failed attempts, escalate to the user with the error details.

**NEVER** mark a task `[x]` without a successful implementation log.
