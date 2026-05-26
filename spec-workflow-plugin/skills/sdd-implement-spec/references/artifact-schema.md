# Artifact Schema

## Contents
- [apiEndpoints](#apiendpoints)
- [components](#components)
- [functions](#functions)
- [classes](#classes)
- [integrations](#integrations)
- [verifications](#verifications)
- [Minimum Viable Artifacts](#minimum-viable-artifacts)

Structured data about implemented artifacts. All artifact types are arrays of objects within the `artifacts` field of the implementation log.

## apiEndpoints

When new API endpoints are created or modified, document each:

| Field | Type | Description |
|-------|------|-------------|
| method | string | HTTP method (GET, POST, PUT, DELETE, PATCH) |
| path | string | Route path (e.g., "/api/specs/:name/logs") |
| purpose | string | What this endpoint does |
| requestFormat | string | Request body/query params format (JSON schema or example) |
| responseFormat | string | Response structure (JSON schema or example) |
| location | string | File path and line number (e.g., "src/server.ts:245") |

```json
{
  "method": "GET",
  "path": "/api/specs/:name/implementation-log",
  "purpose": "Retrieve implementation logs with optional filtering",
  "requestFormat": "Query params: taskId (string, optional), search (string, optional)",
  "responseFormat": "{ entries: ImplementationLogEntry[] }",
  "location": "src/dashboard/server.ts:245"
}
```

## components

When reusable UI components are created, document each:

| Field | Type | Description |
|-------|------|-------------|
| name | string | Component name |
| type | string | Framework type (React, Vue, Svelte, etc.) |
| purpose | string | What the component does |
| location | string | File path |
| props | string | Props interface or type signature |
| exports | array | What it exports (array of export names) |

```json
{
  "name": "LogsPage",
  "type": "React",
  "purpose": "Main dashboard page for viewing implementation logs with search and filtering",
  "location": "src/modules/pages/LogsPage.tsx",
  "props": "{ specs: any[], selectedSpec: string, onSelect: (value: string) => void }",
  "exports": ["LogsPage (default)"]
}
```

## functions

When utility functions are created, document each:

| Field | Type | Description |
|-------|------|-------------|
| name | string | Function name |
| purpose | string | What it does |
| location | string | File path and line |
| signature | string | Function signature (params and return type) |
| isExported | boolean | Whether it can be imported |

```json
{
  "name": "searchLogs",
  "purpose": "Search implementation logs by keyword",
  "location": "src/dashboard/implementation-log-manager.ts:156",
  "signature": "(searchTerm: string) => Promise<ImplementationLogEntry[]>",
  "isExported": true
}
```

## classes

When classes are created, document each:

| Field | Type | Description |
|-------|------|-------------|
| name | string | Class name |
| purpose | string | What the class does |
| location | string | File path |
| methods | array | List of public methods |
| isExported | boolean | Whether it can be imported |

```json
{
  "name": "ImplementationLogManager",
  "purpose": "Manages CRUD operations for implementation logs",
  "location": "src/dashboard/implementation-log-manager.ts",
  "methods": ["loadLog", "addLogEntry", "getAllLogs", "searchLogs", "getTaskStats"],
  "isExported": true
}
```

## integrations

Document how frontend connects to backend:

| Field | Type | Description |
|-------|------|-------------|
| description | string | How components connect to APIs |
| frontendComponent | string | Which component initiates the connection |
| backendEndpoint | string | Which API endpoint is called |
| dataFlow | string | Describe the data flow (e.g., "User clicks → API call → State update → Re-render") |

```json
{
  "description": "LogsPage fetches logs via REST API and subscribes to WebSocket for real-time updates",
  "frontendComponent": "LogsPage",
  "backendEndpoint": "GET /api/specs/:name/implementation-log",
  "dataFlow": "Component mount → API fetch → Display logs → WebSocket subscription → Real-time updates on new entries"
}
```

## verifications

When tasks verify existing code without creating new artifacts:

| Field | Type | Description |
|-------|------|-------------|
| description | string | What was verified |
| scope | string | Files or modules covered (e.g., "tests/test_gate_session.py") |
| result | string | Outcome (e.g., "27 tests passing", "All delegation paths confirmed") |
| location | string | Primary file verified |

```json
{
  "description": "Verified gate-session state transitions cover all approval workflows",
  "scope": "tests/test_gate_session.py, scripts/review_quality/gate_session.py",
  "result": "27 tests passing — all transitions covered",
  "location": "tests/test_gate_session.py"
}
```

## Minimum Viable Artifacts

Every log entry MUST include at least one artifact type. If in doubt, include:
- Any new files → likely a `function`, `class`, or `component`
- Any route handlers → `apiEndpoints`
- Any frontend-backend connections → `integrations`
- Verification-only tasks (no new files) → `verifications`

The artifacts field cannot be an empty object `{}`. At minimum, include the primary artifact type for what was implemented.
