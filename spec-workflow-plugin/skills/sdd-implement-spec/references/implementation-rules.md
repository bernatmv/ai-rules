# Implementation Rules

Critical rules for spec task implementation.

## Contents

- [Sequential Execution](#sequential-execution)
- [Cross-Task Concerns](#cross-task-concerns)
- [Task Markers](#task-markers)
- [Completion Criteria](#completion-criteria)
- [Artifact Requirements](#artifact-requirements)
- [Infrastructure Fix Tracking](#infrastructure-fix-tracking)
- [Multi-File Task Plans](#multi-file-task-plans)
- [Implementation Logging Reference](#implementation-logging-reference)

## Sequential Execution

- Implement one task at a time
- Complete the current task (including logging) before starting the next
- Follow task ordering from tasks.md — dependencies are implicit in order

## Cross-Task Concerns

- Search implementation logs before EVERY task, not just the first
- Later tasks may depend on artifacts created by earlier tasks
- Reuse code from earlier tasks via `_Leverage` fields and log search results
- Do not modify files outside the task's scope without documenting it

## Task Markers

| Marker | Meaning | When to Set |
|--------|---------|-------------|
| `- [ ]` | Pending | Default state |
| `- [-]` | In-progress | Before starting implementation |
| `- [x]` | Complete | Only after log-implementation.py succeeds |

**Never** set `[x]` without a successful implementation log.
**Never** have multiple `[-]` tasks simultaneously.

## Completion Criteria

A task is truly complete when ALL of:
1. Code is implemented per task description
2. Tests pass (unit and integration as applicable)
3. `Success` criteria from `_Prompt` are met
4. `log-implementation.py` returned exit code 0 with artifacts
5. Task marker changed from `[-]` to `[x]` in tasks.md

## Artifact Requirements

Every implementation log MUST include structured artifacts. Artifacts create a searchable knowledge base that prevents future duplication. Include all relevant types:

- `apiEndpoints` — any API routes created or modified
- `components` — any reusable UI components
- `functions` — any utility functions or methods
- `classes` — any classes created
- `integrations` — any frontend-backend connections

Omitting artifacts means future agents will duplicate your work.

## Infrastructure Fix Tracking

If you must fix an SDD infrastructure script (e.g., `log-implementation.py`, `check-pre-existing.py`) to unblock the workflow:

1. Record the fix in the **next task's** implementation log under `files-modified`.
2. If the fix is needed to unblock the **current** task, create a standalone `--task-id "infra-{N}"` log entry FIRST (using the command below), then proceed with the task's own log. This separates infrastructure changes from task implementation for traceability.
3. Include the fix description in the log summary.
4. If no tasks remain, create a standalone log:

```bash
.spec-workflow/sdd util/log-implementation.py \
  --spec-name "{name}" --task-id "infra" \
  --summary "Infrastructure fix: {description}" \
  --files-modified '["{file}"]' \
  --statistics '{"preExisting": true}' \
  --artifacts '{"verifications": [{"description": "Fixed {script}", "scope": "infrastructure", "result": "pass"}]}'
```

## Multi-File Task Plans

Tasks that touch more than a small number of files benefit from an
auditable `edit-plan.json` **before** any files change. The plan forces
the agent to declare scope up-front; validation then catches
out-of-tree edits, `.gitignore` violations, and oversized deltas.

| Setting | Default | Source |
|---------|---------|--------|
| File-count threshold (plan required) | 5 | `sdd_core.edit_plans.DEFAULT_FILE_THRESHOLD` |
| Per-file `size_delta_estimate` cap | 400 lines | `sdd_core.edit_plans.DEFAULT_SIZE_DELTA_THRESHOLD` |
| Allow large delta | opt-in | `validate-plan.py --allow-large-delta` |

**When to run the plan loop**

- Any task whose intended scope includes more than 5 files.
- Any refactor with a `size_delta_estimate` beyond the default cap.
- Any time a reviewer asks "what will this touch?" before approving.

**Loop**

```bash
.spec-workflow/sdd impl/plan-task.py --spec-name NAME --task-id ID \
  --file src/foo.py:modify:120 \
  --file tests/test_foo.py:add \
  --out /tmp/edit-plan.json
.spec-workflow/sdd impl/validate-plan.py /tmp/edit-plan.json
# Apply the plan by performing the edits described in it, then log with
# util/log-implementation.py as usual.
```

Overriding the thresholds is permitted on a per-task basis via
`--threshold` / `--max-size-delta` / `--allow-large-delta`, but the
default values apply across the ecosystem unless a reviewer agrees
otherwise.

## Implementation Logging Reference

> See `$SKILLS/sdd-common/references/telemetry.md` for the canonical logging invocation,
> artifact requirements, and field reference.
