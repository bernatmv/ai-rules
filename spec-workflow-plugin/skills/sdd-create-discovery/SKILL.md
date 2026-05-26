---
name: sdd-create-discovery
description: Manages discovery project scaffolding and manifest metadata for the
  pre-spec phase. Scaffolds discovery project folders, registers PRD and UX flow
  artifacts, links projects to specs, and updates status. Use when asked to create
  a discovery project, add artifacts to a discovery manifest, link a discovery
  project to a spec, update discovery status, or resume a discovery project.
allowed-tools: Read Write Edit Bash Agent AskQuestion AskUserQuestion TaskCreate TaskUpdate WebFetch
metadata:
  version: 3.3.1
  category: development
  dependencies: [sdd-common]
  author: membership-platforms-sdd-guild
---

> **Paths:** See `$SKILLS/sdd-common/references/path-conventions.md`. Scripts: `.spec-workflow/sdd {group}/{script}.py`.

# SDD: Create Discovery

> Uses Python scripts from `sdd-common/scripts/discovery/` via the `.spec-workflow/sdd` shim. No MCP server required.

Manages discovery project folders under `.spec-workflow/discovery/`. A discovery project is a structured home for PRDs, UX flows, and other pre-spec artifacts, with a `manifest.json` tracking metadata and linkages to specs.

## Contents

- [Dependencies](#dependencies)
- [Invocation Examples](#invocation-examples)
- [Workflow: create](#workflow-create)
- [Workflow: add](#workflow-add)
- [Workflow: link](#workflow-link)
- [Workflow: set-artifact-status](#workflow-set-artifact-status)
- [Workflow: set-project-status](#workflow-set-project-status)
- [Workflow: resume](#workflow-resume)
- [Manifest Schema Reference](#manifest-schema-reference)
- [Post-Write Validation](#post-write-validation)
- [Workflow Progress](#workflow-progress)
- [Safety Rules](#safety-rules)
- [Edge Cases](#edge-cases)
- [Completion](#completion)
- [Reference Files](#reference-files)

## Dependencies

> **Load on demand**: Read each file only when the workflow reaches that step — not all upfront.

| Step | File | Kind | Freedom |
|------|------|------|:-:|
| Safety rules | `$SKILLS/sdd-common/references/safety-rules.md` | read | L |
| Edge cases | `$SKILLS/sdd-common/references/common-edge-cases.md` | read | M |
| Schema details (add, link, set-status) | `$SKILLS/sdd-create-discovery/references/manifest-schema.md` | read | M |
| Script patterns | `$SKILLS/sdd-common/references/tool-patterns.md` | read | L |
| Create | `$SKILLS/sdd-common/scripts/discovery/init-project.py` | run | L |
| Add / Link / Set-status | `$SKILLS/sdd-common/scripts/discovery/update-manifest.py` | run | L |
| Post-write validation | `$SKILLS/sdd-common/scripts/discovery/validate-manifest.py` | run | L |
| All | `$SKILLS/sdd-common/references/state-scope.md` (scope + lifetime of persisted state) | read | L |

## Invocation Examples

| Request | Action |
|---------|--------|
| "sdd create discovery {name}" | Scaffold a new discovery project |
| "sdd discovery add {name} {file}" | Register an artifact in the manifest |
| "sdd discovery link {name} {spec} {relationship}" | Link project to a spec |
| "sdd discovery set-artifact-status {name} {file} {status}" | Update artifact status |
| "sdd discovery set-project-status {name} {status}" | Update project-level status |
| "sdd resume discovery {name}" | Resume and display project state |

## Workflow: create

**Command:** `sdd create discovery {name}`

1. **Run init script**:
   ```
   .spec-workflow/sdd discovery/init-project.py --name "{name}"
   ```
   The script validates kebab-case, checks for existing project, creates the folder,
   writes `manifest.json` with defaults via `atomic_write_json`, and verifies the write.
2. **If script returns error**: Display the error message and hint to the user.
3. **On success**: Confirm with the folder path and suggest next steps (add artifacts).

## Workflow: add

**Command:** `sdd discovery add {name} {file}`

> **PRD integration:** When using `sdd-create-prd`, the PRD skill
> auto-registers `prd.md` in the discovery manifest via this command.
> A PRD written outside the SDD workflow can also be manually registered.

1. **Run update script**:
   ```
   .spec-workflow/sdd discovery/update-manifest.py --name "{name}" add-artifact --file "{file}"
   ```
   The script validates file exists, checks for duplicates, auto-detects artifact type
   per `references/manifest-schema.md` § Artifact Type Detection Rules, appends to the
   artifacts array, refreshes `updatedAt`, and writes atomically.
2. **If script returns error**: Display the error message and hint to the user.
3. **On success**: Confirm with the registered file, detected type, and project name.

## Workflow: link

**Command:** `sdd discovery link {name} {spec-name} {relationship}`

1. **Run update script**:
   ```
   .spec-workflow/sdd discovery/update-manifest.py --name "{name}" add-spec-link --spec "{spec-name}" --relationship "{relationship}"
   ```
   The script validates relationship value, checks for duplicate spec links, appends
   to the specs array, refreshes `updatedAt`, and writes atomically.
2. **If script returns error**: Display the error message and hint to the user.
3. **On success**: Confirm with the linked spec name and relationship.

## Workflow: set-artifact-status

**Command:** `sdd discovery set-artifact-status {name} {file} {status}`

1. **Run update script**:
   ```
   .spec-workflow/sdd discovery/update-manifest.py --name "{name}" set-artifact-status --file "{file}" --status "{status}"
   ```
2. **If script returns error**: Display the error message and hint.
3. **On success**: Confirm with updated file and status.

## Workflow: set-project-status

**Command:** `sdd discovery set-project-status {name} {status}`

1. **Run update script**:
   ```
   .spec-workflow/sdd discovery/update-manifest.py --name "{name}" set-project-status --status "{status}"
   ```
2. **If script returns error**: Display the error message and hint.
3. **On success**: Confirm with updated project status.

## Workflow: resume

**Command:** `sdd resume discovery {name}`

1. **Check folder exists**: If `.spec-workflow/discovery/{name}/` doesn't exist, error.
2. **Validate manifest**:
   ```
   .spec-workflow/sdd discovery/validate-manifest.py --name "{name}"
   ```
   If validation fails or manifest is missing, offer to create a fresh one via `init-project.py`.
3. **Read and display current state**:
   - Project name and status
   - Owner (if set)
   - Timestamps (created, last updated)
   - Artifacts table: file, type, status
   - Linked specs table: name, relationship
4. **Detect unregistered files**: List `.md` files in the project folder not in the `artifacts` array. If found, offer to register each one via `update-manifest.py add-artifact`.

## Manifest Schema Reference

See `references/manifest-schema.md` for the complete schema, field constraints, artifact type detection rules, valid status values, and the portal contract.

## Post-Write Validation

All scripts use `sdd_core.output.atomic_write_json()` with `verify_key` for crash-safe
writes with read-back verification. For explicit full validation:

```
.spec-workflow/sdd discovery/validate-manifest.py --name "{name}"
```

Run after the resume workflow or if a manifest may be corrupt.

## Workflow Progress

For multi-command sessions, copy this checklist:

```
Discovery Progress:
- [ ] Create project folder and manifest (init-project.py — validates name, atomic write)
- [ ] Add artifacts (repeat per file) (update-manifest.py — duplicate check + type detection)
- [ ] Link to spec(s) (update-manifest.py — duplicate check + relationship validation)
- [ ] Update statuses as reviews progress (update-manifest.py — status validation)
- [ ] Resume to verify final state (validate-manifest.py — full schema check)
```

## Safety Rules

See `$SKILLS/sdd-common/references/safety-rules.md`. Key rules for this skill: Read-modify-write for manifest updates; no overwrite on create; idempotent duplicate warnings; preserve files on recovery.

On any blocked/pending-calls response from a downstream PRD or spec launch, follow `$SKILLS/sdd-common/references/review-approval-pipeline.md` § Pending Tool Calls Enforcement (covers `required_tool_calls` ordering and `next_action_sequence` recovery).

## Edge Cases

See `$SKILLS/sdd-common/references/common-edge-cases.md` for shared patterns (Resume Existing, Project/Resource Already Exists). Skill-specific edge cases:

| Situation | Action |
|-----------|--------|
| Project name not kebab-case | Reject with naming convention error and example |
| Duplicate artifact on add | Warn, no-op |
| Duplicate spec link on link | Warn, no-op |
| Invalid status value | Reject with list of valid values for the target |
| Artifact not found on set-artifact-status | Error with list of registered artifacts |
| Empty project folder on resume | Show empty state, suggest adding files |

## Completion

Discovery project scaffolding complete. To create a PRD, run `sdd create prd {name}`.

## Reference Files

- `references/manifest-schema.md` — Discovery manifest JSON schema, field constraints, artifact type detection rules

## Handoffs

See `references/handoffs.md` (generated from `$SCRIPTS/handoff-registry.json`).
Regenerate via `.spec-workflow/sdd internal_lints/skill_md_handoff_table.py --rewrite`.
