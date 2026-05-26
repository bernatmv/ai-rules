# Artifact Examples

## Contents
- [Good Example (Include ALL relevant artifacts)](#good-example-include-all-relevant-artifacts)
- [Bad Examples (Don't do this)](#bad-examples-dont-do-this)
- [Logging Checklist](#logging-checklist)

## Good Example (Include ALL relevant artifacts)

Task: "Implemented logs dashboard with real-time updates"

```json
{
  "taskId": "2.3",
  "summary": "Implemented real-time implementation logs dashboard with filtering, search, and WebSocket updates",
  "artifacts": {
    "apiEndpoints": [
      {
        "method": "GET",
        "path": "/api/specs/:name/implementation-log",
        "purpose": "Retrieve implementation logs with optional filtering",
        "requestFormat": "Query params: taskId (string, optional), search (string, optional)",
        "responseFormat": "{ entries: ImplementationLogEntry[] }",
        "location": "src/dashboard/server.ts:245"
      }
    ],
    "components": [
      {
        "name": "LogsPage",
        "type": "React",
        "purpose": "Main dashboard page for viewing implementation logs with search and filtering",
        "location": "src/modules/pages/LogsPage.tsx",
        "props": "None (uses React Router params)",
        "exports": ["LogsPage (default)"]
      }
    ],
    "classes": [
      {
        "name": "ImplementationLogManager",
        "purpose": "Manages CRUD operations for implementation logs",
        "location": "src/dashboard/implementation-log-manager.ts",
        "methods": ["loadLog", "addLogEntry", "getAllLogs", "searchLogs", "getTaskStats"],
        "isExported": true
      }
    ],
    "integrations": [
      {
        "description": "LogsPage fetches logs via REST API and subscribes to WebSocket for real-time updates",
        "frontendComponent": "LogsPage",
        "backendEndpoint": "GET /api/specs/:name/implementation-log",
        "dataFlow": "Component mount → API fetch → Display logs → WebSocket subscription → Real-time updates on new entries"
      }
    ]
  },
  "filesModified": ["src/dashboard/server.ts"],
  "filesCreated": ["src/modules/pages/LogsPage.tsx"],
  "statistics": { "linesAdded": 650, "linesRemoved": 15, "filesChanged": 2 }
}
```

## Bad Examples (Don't do this)

### Empty artifacts — future agents learn nothing

```json
{
  "taskId": "2.3",
  "summary": "Added endpoint and page",
  "artifacts": {},
  "filesModified": ["server.ts"],
  "filesCreated": ["LogsPage.tsx"]
}
```

**Why it's bad**: No structured data. Future agents searching for API endpoints, components, or integration patterns will find nothing. They will create duplicates.

### Vague summary with no structured data

```json
{
  "taskId": "2.3",
  "summary": "Implemented features",
  "artifacts": {},
  "filesModified": ["server.ts", "app.tsx"]
}
```

**Why it's bad**: "Implemented features" tells nothing about what was built. No file paths, no signatures, no searchable content.

### Missing integration artifacts

```json
{
  "taskId": "2.3",
  "summary": "Added API endpoint and React page",
  "artifacts": {
    "apiEndpoints": [
      {
        "method": "GET",
        "path": "/api/logs",
        "purpose": "Get logs",
        "location": "server.ts"
      }
    ]
  },
  "filesModified": ["server.ts"],
  "filesCreated": ["LogsPage.tsx"]
}
```

**Why it's bad**: Created a React component (`LogsPage.tsx`) but didn't document it. Created a frontend-backend connection but didn't document the integration. Missing `requestFormat`/`responseFormat` on the endpoint.

## Logging Checklist

Before calling `log-implementation.py`, verify:

- [ ] Summary is specific (not "implemented features" — describe WHAT)
- [ ] All API endpoints have method, path, purpose, request/response format, location
- [ ] All UI components have name, type, purpose, location, props, exports
- [ ] All functions have name, purpose, location, signature, isExported
- [ ] All classes have name, purpose, location, methods, isExported
- [ ] All frontend-backend connections have integration entries
- [ ] File paths in `location` fields include line numbers where practical
- [ ] `filesModified` and `filesCreated` are accurate and complete
- [ ] `statistics` (linesAdded, linesRemoved) are reasonable estimates
