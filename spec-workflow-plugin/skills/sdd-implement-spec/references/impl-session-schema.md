# Implementation Session Schema

Session file: `.spec-workflow/specs/{spec-name}/.impl-session.json`

Managed by `impl/impl_session.py`. Loaded on resume or troubleshooting — not required for normal forward execution.

## Contents

- [Schema](#schema)
- [State Transitions](#state-transitions)
- [Enforcement Rules](#enforcement-rules)

## Schema

```json
{
  "schema_version": "1.0.0",
  "spec_name": "string",
  "started_at": "ISO 8601 UTC",
  "updated_at": "ISO 8601 UTC",
  "execution_mode": "verification-only | standard",
  "batch_result": {
    "all_pre_existing": "boolean",
    "checked_count": "integer",
    "determined_at": "ISO 8601 UTC"
  },
  "current_task": {
    "id": "string (task ID)",
    "status": "in_progress",
    "started_at": "ISO 8601 UTC"
  },
  "completed_tasks": [
    {
      "id": "string",
      "logged_at": "ISO 8601 UTC",
      "log_id": "string (8-char hex from log-implementation.py)",
      "pre_existing": "boolean"
    }
  ],
  "test_results": {
    "last_run": "ISO 8601 UTC",
    "passed": "integer",
    "failed": "integer"
  },
  "review_status": "null | skipped | passed | needs_work"
}
```

## State Transitions

| From | To | Trigger |
|------|-----|---------|
| No file | Fresh session | `init_session()` |
| `current_task: null` | `current_task: {id, in_progress}` | `record_task_start()` |
| `current_task: {id}` | `current_task: null`, entry in `completed_tasks` | `record_task_complete()` |
| Stale `current_task` | `current_task: null` | `init_session()` on resume (auto-reset) |

## Enforcement Rules

- `record_task_start` refuses if another task is in-progress
- `record_task_start` refuses if the last completed task has no `log_id`
- `record_task_complete` refuses if `current_task.id` doesn't match
- `advance-task.py --action finish` refuses if log file not found on disk
