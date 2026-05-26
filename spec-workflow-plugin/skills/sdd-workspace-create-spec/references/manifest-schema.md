# Manifest & Tracker Schema Reference

## Contents

- [coordination-manifest.json Schema](#coordination-manifestjson-schema)
- [workspace-tracker.json Schema](#workspace-trackerjson-schema)
- [Status Lifecycle](#status-lifecycle)
- [Validation Rules](#validation-rules)

## coordination-manifest.json Schema

Stored at `.spec-workflow/workspace/{feature}/coordination-manifest.json`.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `schemaVersion` | string | Yes | Schema version, currently `"2.0.0"` |
| `feature` | string | Yes | Feature/workspace name (kebab-case) |
| `repos` | array | Yes | All repositories including coordinator (see `repoType`) |
| `repos[].id` | string | Yes | Unique repo identifier (used in task metadata) |
| `repos[].name` | string | Yes | Repository display name |
| `repos[].path` | string | Yes | Absolute path to repo |
| `repos[].role` | string | Yes (post-bootstrap) | Free-form description of what this repo contributes. Bootstrap (`workspace/init-feature.py`) leaves this `""`; populate via `.spec-workflow/sdd workspace/update-manifest.py --target {feature} set-repo-role --repo-id ID --role "..."`. `extract-delegation.py` warns until set. |
| `repos[].repoType` | string | Yes | `"coordinator"` or `"target"` — exactly one coordinator per workspace. Set by the `init-feature.py --repo` locator's first segment; immutable post-bootstrap. |
| `repos[].subSpec` | string | Yes | Sub-spec name to create in this repo (coordinator: equals `feature`) |
| `repos[].skipPhases` | array | No | Phases to skip (values: `"requirements"`, `"design"`, `"tasks"`). Coordinator always `[]`. |
| `workflow` | object | No | Workflow configuration |
| `workflow.mode` | string | No | Workflow mode: `"batch-by-doc-type"` (default) or `"vertical"` |
| `workflow.phaseOrder` | array | No | Phase execution order (default: `["requirements", "design", "tasks"]`) |
| `createdAt` | string | Yes | ISO 8601 UTC timestamp |
| `status` | string | Yes | `"active"`, `"completed"`, or `"cancelled"` |

Every repo (coordinator included) is a regular entry in `repos[]`, distinguished by
`repoType`. The coordinator is always first in the list. Helper functions
`get_coordinator(manifest)` and `get_target_repos(manifest)` provide filtered
access when needed.

**Example:**

```json
{
  "schemaVersion": "2.0.0",
  "feature": "user-authentication",
  "repos": [
    {
      "id": "sdd-core-service",
      "name": "sdd-core-service",
      "path": "/Users/dev/projects/sdd-core-service",
      "role": "Orchestration, shared auth config, integration tests",
      "repoType": "coordinator",
      "subSpec": "user-authentication"
    },
    {
      "id": "backend",
      "name": "backend-api",
      "path": "/Users/dev/projects/backend-api",
      "role": "API endpoints, auth middleware, JWT token management",
      "repoType": "target",
      "subSpec": "user-auth-backend"
    },
    {
      "id": "frontend",
      "name": "frontend-web",
      "path": "/Users/dev/projects/frontend-web",
      "role": "Auth UI, token storage, route guards",
      "repoType": "target",
      "subSpec": "user-auth-frontend"
    },
    {
      "id": "shared-types",
      "name": "shared-types",
      "path": "/Users/dev/projects/shared-types",
      "role": "TypeScript type definitions — no runtime code",
      "repoType": "target",
      "subSpec": "user-auth-types",
      "skipPhases": ["tasks"]
    }
  ],
  "workflow": {
    "mode": "batch-by-doc-type",
    "phaseOrder": ["requirements", "design", "tasks"]
  },
  "createdAt": "2026-03-20T10:00:00.000Z",
  "status": "active"
}
```

## workspace-tracker.json Schema

Stored at `.spec-workflow/workspace/{feature}/workspace-tracker.json`.

**Naming convention:** "sub-spec" in prose; `subSpec`/`subSpecs` in JSON keys.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `schemaVersion` | string | Yes | `"2.0.0"` |
| `feature` | string | Yes | Feature name (matches manifest) |
| `status` | string | Yes | Overall workspace status: `in_progress`, `completed`, `blocked`, `cancelled` |
| `currentPhase` | string | No | Current document phase: `"requirements"`, `"design"`, `"tasks"`, or `"complete"` |
| `createdAt` | string | Yes | ISO 8601 creation timestamp |
| `updatedAt` | string | Yes | ISO 8601 last update timestamp |
| `phaseGates` | object | No | Phase-level completion checkpoints |
| `phaseGates.requirements` | object\|null | | `{ reviewedAt, approvedAt, reposApproved, reposSkipped, reposFailed }` |
| `phaseGates.design` | object\|null | | Same shape as `phaseGates.requirements` |
| `phaseGates.tasks` | object\|null | | Same shape as `phaseGates.requirements` |
| `subSpecs` | array | Yes | Per-repo entries (coordinator + targets) |
| `subSpecs[].repoId` | string | Yes | Matches manifest `repos[].id` |
| `subSpecs[].repoName` | string | | Repository display name |
| `subSpecs[].repoPath` | string | | Absolute path to repo |
| `subSpecs[].subSpecName` | string | | Sub-spec name in repo |
| `subSpecs[].repoType` | string | Yes | `"coordinator"` or `"target"` (mirrors manifest) |
| `subSpecs[].status` | string | Yes | Current status (see lifecycle below) |
| `subSpecs[].phase` | string | | Current spec phase |
| `subSpecs[].docStatus` | object | No | Per-document creation lifecycle |
| `subSpecs[].docStatus.requirements` | string | | `"pending"`, `"created"`, `"validated"`, `"reviewed"`, `"approved"`, `"skipped"`, `"failed"`, `"revision_requested"` |
| `subSpecs[].docStatus.design` | string | | Same values as `docStatus.requirements` |
| `subSpecs[].docStatus.tasks` | string | | Same values as `docStatus.requirements` |
| `subSpecs[].reviewMeta` | object | No | Per-phase review audit trail |
| `subSpecs[].reviewMeta.{phase}.reviewSkipped` | bool | | `true` when user chose "Skip review" |
| `subSpecs[].reviewMeta.{phase}.reviewSkippedAt` | string | | ISO 8601 timestamp of skip decision |
| `subSpecs[].approvals` | object | No | Per-document approval state |
| `subSpecs[].approvals.requirements` | object | | `{ approvalId, status, timestamp }` |
| `subSpecs[].approvals.design` | object | | `{ approvalId, status, timestamp }` |
| `subSpecs[].approvals.tasks` | object | | `{ approvalId, status, timestamp }` |
| `subSpecs[].lastChecked` | string | | ISO 8601 last poll timestamp |
| `subSpecs[].autoGenerated` | bool | | `true` when sub-spec was generated from delegation context without manual editing. Does NOT affect approval requirements. |
| `summary` | object | Yes | Aggregated progress |
| `summary.totalSubSpecs` | int | Yes | Total sub-specs |
| `summary.completed` | int | Yes | Completed sub-specs |
| `summary.inProgress` | int | Yes | In-progress sub-specs |
| `summary.pending` | int | Yes | Pending sub-specs |
| `summary.specCreated` | int | Yes | Sub-specs with spec created |
| `summary.requirementsCreated` | int | | Sub-specs with requirements created |
| `summary.requirementsApproved` | int | | Sub-specs with requirements approved |
| `summary.designCreated` | int | | Sub-specs with design created |
| `summary.designApproved` | int | | Sub-specs with design approved |
| `summary.tasksCreated` | int | | Sub-specs with tasks created |
| `summary.approved` | int | Yes | Approved sub-specs (awaiting implementation) |
| `summary.rejected` | int | Yes | Rejected sub-specs |
| `summary.approvedSubSpecs` | int | Yes | Sub-specs with all 3 docs approved |
| `summary.blocked` | int | Yes | Blocked sub-specs |
| `summary.failed` | int | Yes | Failed sub-specs |
| `summary.cancelled` | int | Yes | Cancelled sub-specs |
| `summary.byPhase` | object | No | Per-phase status counts (present when `docStatus` fields exist) |
| `summary.byPhase.requirements` | object | | `{ pending, created, validated, reviewed, approved, skipped, failed }` |
| `summary.byPhase.design` | object | | Same shape |
| `summary.byPhase.tasks` | object | | Same shape |

**Approval status lifecycle:** `not_requested` → `pending` → `approved` | `revision_requested` | `rejected`

**docStatus lifecycle:** `pending` → `created` → `validated` → `reviewed` → `approved` (or `skipped` / `failed` / `revision_requested`)

**Relationship between `docStatus` and `approvals`:**
- `docStatus` tracks the *creation lifecycle* (created → validated → approved)
- `approvals` tracks the *formal approval artifact* (approvalId, timestamp)
- `docStatus.requirements = "approved"` means the phase gate passed
- `approvals.requirements.approvalId` records the audit artifact

**Example (mid Phase D):**

```json
{
  "schemaVersion": "2.0.0",
  "feature": "user-authentication",
  "status": "in_progress",
  "currentPhase": "design",
  "createdAt": "2026-03-20T10:00:00.000Z",
  "updatedAt": "2026-03-20T14:30:00.000Z",
  "phaseGates": {
    "requirements": {
      "reviewedAt": "2026-03-20T11:00:00.000Z",
      "approvedAt": "2026-03-20T11:05:00.000Z",
      "reposApproved": ["sdd-core-service", "backend", "frontend"],
      "reposSkipped": [],
      "reposFailed": []
    },
    "design": null,
    "tasks": null
  },
  "subSpecs": [
    {
      "repoId": "sdd-core-service",
      "repoName": "sdd-core-service",
      "repoPath": "/Users/dev/projects/sdd-core-service",
      "subSpecName": "user-authentication",
      "repoType": "coordinator",
      "status": "design_created",
      "phase": "design",
      "docStatus": {
        "requirements": "approved",
        "design": "created",
        "tasks": "pending"
      },
      "approvals": {
        "requirements": { "approvalId": "approval_001", "status": "approved", "timestamp": "2026-03-20T11:00:00.000Z" },
        "design": { "approvalId": null, "status": "not_requested", "timestamp": null },
        "tasks": { "approvalId": null, "status": "not_requested", "timestamp": null }
      }
    },
    {
      "repoId": "backend",
      "repoName": "backend-api",
      "repoPath": "/Users/dev/projects/backend-api",
      "subSpecName": "user-auth-backend",
      "repoType": "target",
      "status": "design_created",
      "phase": "design",
      "docStatus": {
        "requirements": "approved",
        "design": "created",
        "tasks": "pending"
      },
      "approvals": {
        "requirements": { "approvalId": "approval_002", "status": "approved", "timestamp": "2026-03-20T11:00:00.000Z" },
        "design": { "approvalId": null, "status": "not_requested", "timestamp": null },
        "tasks": { "approvalId": null, "status": "not_requested", "timestamp": null }
      },
      "autoGenerated": true,
      "lastChecked": "2026-03-20T14:30:00.000Z"
    }
  ],
  "summary": {
    "totalSubSpecs": 2,
    "completed": 0,
    "inProgress": 0,
    "designCreated": 2,
    "requirementsApproved": 2,
    "pending": 0,
    "specCreated": 0,
    "approved": 0,
    "rejected": 0,
    "blocked": 0,
    "failed": 0,
    "cancelled": 0,
    "approvedSubSpecs": 0,
    "byPhase": {
      "requirements": { "approved": 2 },
      "design": { "created": 2 },
      "tasks": { "pending": 2 }
    }
  }
}
```

## Status Lifecycle

Sub-spec status transitions follow a defined state machine. The v2.0.0 schema adds
`repoType` to each `subSpecs[]` entry but uses the same status transitions as v1.2.0.

### v1.2.0+ Phase-Based Flow (batch-by-doc-type)

```
pending → requirements_created → requirements_approved
  → design_created → design_approved
  → tasks_created → approved → in_progress → completed
                                    ↓    ↓
                                 blocked  failed
                                    ↓    ↓
                                 in_progress

     any → cancelled
```

### v1.1.0 Vertical Flow (backward compatible)

```
pending → spec_created → approved → in_progress → completed
              ↓                         ↓    ↓
           rejected                  blocked  failed
              ↓                         ↓    ↓
         spec_created              in_progress

     any → cancelled
```

**Transition table** (derived from `VALID_TRANSITIONS` in `workspace_tracker.py`):

| From | Allowed Targets |
|------|----------------|
| `pending` | `spec_created`, `requirements_created`, `cancelled` |
| `spec_created` | `approved`, `rejected`, `cancelled` |
| `rejected` | `spec_created`, `cancelled` |
| `requirements_created` | `requirements_approved`, `cancelled` |
| `requirements_approved` | `design_created`, `cancelled` |
| `design_created` | `design_approved`, `cancelled` |
| `design_approved` | `tasks_created`, `cancelled` |
| `tasks_created` | `approved`, `cancelled` |
| `approved` | `in_progress`, `cancelled` |
| `in_progress` | `completed`, `blocked`, `failed`, `cancelled` |
| `blocked` | `in_progress`, `cancelled` |
| `failed` | `in_progress`, `cancelled` |
| `completed` | _(terminal)_ |
| `cancelled` | _(terminal)_ |

### docStatus Lifecycle

Per-document creation lifecycle tracked in `subSpecs[].docStatus`:

```
pending → created → validated → reviewed → approved
  ↓                      ↓          ↓
skipped              revision_requested → created (retry)
                         ↑
                      failed → pending (retry)
```

| From | Allowed Targets |
|------|----------------|
| `pending` | `created`, `skipped` |
| `created` | `validated`, `failed` |
| `validated` | `reviewed`, `revision_requested` |
| `reviewed` | `approved`, `revision_requested` |
| `approved` | _(terminal for this phase)_ |
| `skipped` | _(terminal)_ |
| `failed` | `pending` (retry) |
| `revision_requested` | `created` (revise) |

Invalid transitions are rejected by `workspace/update-tracker.py` with an error
listing the valid target states.

> **Source of truth:** `VALID_TRANSITIONS` and `DOC_STATUS_TRANSITIONS` in
> `sdd_core/workspace_tracker.py` and `sdd_core/workspace_phase.py` are the
> authoritative definitions. This section is a human-readable mirror.

## Validation Rules

`validate_manifest()` in `sdd_core/workspace_manifest.py` checks:

| Rule | Severity | Condition |
|------|----------|-----------|
| `manifest-feature` | error | `feature` field missing or empty |
| `manifest-schemaVersion` | error | `schemaVersion` field missing or empty |
| `manifest-status` | error | `status` not in `["active", "completed", "cancelled"]` |
| `manifest-repos` | error | `repos` array missing or has fewer than 2 entries |
| `manifest-repo-id` | error | Repo entry missing `id` field |
| `manifest-repo-name` | error | Repo entry missing `name` field |
| `manifest-repo-path` | error | Repo entry missing `path` field |
| `manifest-repo-role` | error | Repo entry missing `role` field |
| `manifest-repo-subSpec` | error | Repo entry missing `subSpec` field |
| `manifest-repo-repoType` | error | Repo `repoType` not in `["coordinator", "target"]` |
| `manifest-exactly-one-coordinator` | error | Not exactly one entry with `repoType == "coordinator"` |
| `manifest-coordinator-subSpec` | error | Coordinator's `subSpec` does not equal `feature` |
| `manifest-repo-path-exists` | warning | Repo `path` does not exist on disk |
| `manifest-repo-skipPhases` | error | `skipPhases` value not in `["requirements", "design", "tasks"]` |
| `manifest-repo-skipPhases-type` | error | `skipPhases` is not a list |
| `manifest-coordinator-skipPhases` | error | Coordinator has non-empty `skipPhases` |
| `manifest-workflow-mode` | error | `workflow.mode` not in `["batch-by-doc-type", "vertical"]` |
| `manifest-workflow-phaseOrder` | error | `workflow.phaseOrder` value not in `["requirements", "design", "tasks"]` |
| `manifest-workflow-phaseOrder-unique` | error | Duplicate value in `workflow.phaseOrder` |
| `manifest-workflow-phaseOrder-type` | error | `workflow.phaseOrder` is not a list |
