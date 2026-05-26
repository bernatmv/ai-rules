# Discovery Manifest Schema Reference

Single source of truth for the `.spec-workflow/discovery/{name}/manifest.json` schema. Referenced by `SKILL.md`, the spec documents (requirements.md, design.md), and the portal's `discoverySyncService`.

## Contents

- [Field Reference](#field-reference)
- [Project Status Values](#project-status-values)
- [Artifact Status Values](#artifact-status-values)
- [Artifact Type Detection Rules](#artifact-type-detection-rules)
- [Specs Array Schema](#specs-array-schema)
- [Constraints](#constraints)
- [Portal Contract](#portal-contract)
- [Complete Example](#complete-example)

## Field Reference

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `schemaVersion` | string | Yes | Schema version for forward-compatible migrations. Currently `"1.0.0"`. |
| `name` | string | Yes | Discovery project name. Must be kebab-case. |
| `status` | string | Yes | Project-level status. See § Project Status Values. |
| `owner` | string | No | Person or team responsible. Empty string if unset. |
| `createdAt` | string | Yes | ISO 8601 UTC timestamp of project creation. |
| `updatedAt` | string | Yes | ISO 8601 UTC timestamp of last modification. Refreshed on every write. |
| `specs` | array | Yes | Linked spec references. See § Specs Array Schema. May be empty. |
| `artifacts` | array | Yes | Registered artifact entries. See below. May be empty. |

### Artifact Entry Schema

Each entry in the `artifacts` array:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | string | Yes | Filename (not path) of the artifact within the project folder. |
| `type` | string | Yes | Auto-detected artifact type. See § Artifact Type Detection Rules. |
| `status` | string | Yes | Artifact-level status. See § Artifact Status Values. |

## Project Status Values

| Value | Description |
|-------|-------------|
| `draft` | Initial state. Project is being set up, artifacts being gathered. |
| `in-review` | Artifacts are under review by stakeholders. |
| `approved` | Discovery is complete, ready for spec creation. |
| `archived` | Project is no longer active. |

## Artifact Status Values

| Value | Description |
|-------|-------------|
| `draft` | Initial state when artifact is registered. |
| `in-review` | Artifact is under stakeholder review. |
| `approved` | Artifact has been reviewed and approved. |

Note: `archived` is valid at the project level only, not for individual artifacts.

## Artifact Type Detection Rules

Type is auto-detected from the filename. This is the canonical mapping table — the portal trusts the `type` field written by this skill and does NOT re-detect.

| Filename Pattern | Detected Type | Description |
|------------------|---------------|-------------|
| Contains `prd` (case-insensitive) | `prd` | Product Requirements Document |
| Contains `ux-flow` or `ux_flow` (case-insensitive) | `ux-flow` | UX flow diagram or description |
| Contains `wireframe` (case-insensitive) | `wireframe` | Wireframe document |
| Contains `research` (case-insensitive) | `research` | User/market research |
| Contains `competitive` or `comparison` (case-insensitive) | `competitive-analysis` | Competitive analysis |
| None of the above | `supplementary` | Catch-all for unrecognized filenames |

**Detection order:** Check patterns top-to-bottom; first match wins. The `supplementary` catch-all ensures new artifact types can be added by updating this table without breaking existing manifests.

## Specs Array Schema

Each entry in the `specs` array:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Spec name (matches a folder under `.spec-workflow/specs/`). |
| `relationship` | string | Yes | How this spec relates to the discovery project. Valid values: `prd`, `ux-flow`. |

Uniqueness constraint: the combination of `name` + `relationship` must be unique within the array.

## Constraints

| Rule | Detail |
|------|--------|
| **Project name** | Must match `^[a-z0-9]+(-[a-z0-9]+)*$` (kebab-case). |
| **Timestamps** | ISO 8601 UTC format (e.g., `2026-04-01T12:00:00.000Z`). |
| **`updatedAt` freshness** | Must be updated to the current operation's timestamp on every manifest write. |
| **Artifact `file` uniqueness** | No two entries in `artifacts` may share the same `file` value. |
| **Spec link uniqueness** | No two entries in `specs` may share the same `name` + `relationship` pair. |
| **Read-modify-write** | Always read the full manifest, modify in memory, write the full object. No partial file writes. |
| **Status values** | Project status must be one of § Project Status Values. Artifact status must be one of § Artifact Status Values. |

## Portal Contract

> **Maintainer note:** Changes to this section must be coordinated with `sdd-control-panel/packages/server/src/services/discoverySyncService.ts`.

The portal's `discoverySyncService` (in sdd-control-panel) reads manifests created by this skill. This section defines the contract between the two systems.

### Required Fields

The portal requires these fields for display and filtering:
- `name` — used as the project display name
- `status` — used for filtering and status badge display

### Optional Fields

The portal handles these gracefully when missing:
- `owner` — displays "Unassigned" when empty or absent
- `schemaVersion` — portal does not validate the version; treats missing as acceptable

### Arrays

- `specs` and `artifacts` — portal reads both but tolerates empty (`[]`) or missing arrays
- Missing arrays are treated as empty

### Status Values

- Portal stores status as `String` (not enum) and displays as colored badges
- All status values must be lowercase kebab-case
- The portal does NOT validate status values against this schema — it displays whatever is stored

### Type Detection

- Portal does NOT re-detect artifact types from filenames
- It trusts the `type` field in each artifact entry as written by this skill
- Unknown types are displayed with a generic icon

### Malformed Manifests

When the portal encounters a manifest that fails JSON parsing or is missing required fields:
- Falls back to `isStructured = false`
- Infers artifacts from filenames in the project folder
- Displays a warning indicator on the project card

## Complete Example

```json
{
  "schemaVersion": "1.0.0",
  "name": "user-onboarding",
  "status": "in-review",
  "owner": "pm-team",
  "createdAt": "2026-04-01T10:00:00.000Z",
  "updatedAt": "2026-04-02T15:30:00.000Z",
  "specs": [
    {
      "name": "onboarding-flow",
      "relationship": "prd"
    },
    {
      "name": "onboarding-flow",
      "relationship": "ux-flow"
    }
  ],
  "artifacts": [
    {
      "file": "prd-onboarding-v2.md",
      "type": "prd",
      "status": "approved"
    },
    {
      "file": "ux-flow-signup.md",
      "type": "ux-flow",
      "status": "in-review"
    },
    {
      "file": "competitive-analysis.md",
      "type": "competitive-analysis",
      "status": "draft"
    },
    {
      "file": "meeting-notes.md",
      "type": "supplementary",
      "status": "draft"
    }
  ]
}
```
