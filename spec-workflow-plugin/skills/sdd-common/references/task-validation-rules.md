# Task Validation Rules

Canonical merged rule set documenting all validation rules, their severity, and source origin.


## Contents

- [Invocation](#invocation)
- [Checkbox Format (Error)](#checkbox-format-error)
- [Task ID Format (Error)](#task-id-format-error)
- [Metadata Format (Error)](#metadata-format-error)
- [_Requirements: Format (Error)](#_requirements-format-error)
- [_Prompt Closing Underscore (Error)](#_prompt-closing-underscore-error)
- [_Prompt Required Sections (Error)](#_prompt-required-sections-error)
- [_Prompt Required Prefix (Warning)](#_prompt-required-prefix-warning)
- [Lifecycle Step Ordering (Warning)](#lifecycle-step-ordering-warning)
- [Contradiction Detection (Warning)](#contradiction-detection-warning)
- [Severity Levels](#severity-levels)
- [Task Completeness Checks](#task-completeness-checks)
- [Workspace Task Metadata](#workspace-task-metadata)

## Invocation

Copy verbatim; substitute only the `{braced}` tokens.

```
.spec-workflow/sdd spec/lint-tasks.py --target "{spec-name}" --workspace .
.spec-workflow/sdd spec/check-traceability.py --target "{spec-name}" --workspace .
```

`--help` lists available flags. No `--verbose` / `--raw` / other common-CLI flags exist on these scripts; do not pass them.

## Checkbox Format (Error)

- Tasks MUST use `- [ ]`, `- [-]`, or `- [x]` format
- Asterisk format (`* [ ]`) is NOT allowed — dash only
- Source: task-validator.ts

## Task ID Format (Error)

- Each task MUST have a numeric ID matching pattern `\d+(?:\.\d+)*`
- Examples: `1`, `1.2`, `3.1.4`
- Source: task-validator.ts

## Metadata Format (Error)

- Metadata fields use underscore prefix + colon: `_Requirements:`, `_Leverage:`, `_Prompt:`
- Source: task-validator.ts

## _Requirements: Format (Error)

- Value MUST be a comma-separated list of numeric refs matching `\d+(?:\.\d+)*` (e.g. `1.1, 2.3, 5`).
- Non-numeric tokens (e.g. `NFR Reliability`, `PRD § 8`) are parsed as orphan refs and fail `spec/check-traceability.py`.
- Cross-document prose (NFR category, PRD section) belongs in the `_Prompt` body, not in `_Requirements:`.
- Source: `spec/check-traceability.py::REQ_ID_RE`.

## _Prompt Closing Underscore (Error)

- `_Prompt` field MUST end with closing `_`
- Source: task-validator.ts

## _Prompt Required Sections (Error)

- `_Prompt` MUST contain sections: Role, Task, Restrictions, Success
- Source: task-validator.ts, lint-tasks.py

## _Prompt Required Prefix (Warning)

- `_Prompt` SHOULD start with "Implement the task for spec..."
- Source: lint-tasks.py

## Lifecycle Step Ordering (Warning)

Steps must appear in order within `_Prompt`:
1. Mark in-progress (`[-]`)
2. Search Implementation Logs
3. Call log-implementation
4. Mark complete (`[x]`)

Source: lint-tasks.py

## Contradiction Detection (Warning)

- Flag contradictions like "after implementing...before starting"
- Source: lint-tasks.py

## Severity Levels

| Severity | Effect | Examples |
|----------|--------|----------|
| Error | Blocks approval | Missing checkbox, invalid ID, missing sections |
| Warning | Advisory only | Missing prefix, misordered lifecycle, contradictions |

## Task Completeness Checks

### Requirements Traceability
Every acceptance criterion in requirements.md SHOULD map to at least one task
that directly addresses it. Pay special attention to UI/UX criteria — forms,
navigation changes, and pre-population behaviors often need dedicated tasks.

### Testing Strategy Coverage
If design.md § Testing Strategy lists test categories (unit, integration, E2E),
each category SHOULD have at least one corresponding task in tasks.md. If a
category is intentionally deferred, note it:
`<!-- Deferred: E2E tests in follow-up spec -->`

## Workspace Task Metadata

Workspace coordination tasks use the existing `_Key: Value_` italic metadata syntax.
These fields are validated by `.spec-workflow/sdd workspace/check-spec-shape.py` (not by `.spec-workflow/sdd spec/lint-tasks.py`).

| Field | Format | Validation | Purpose |
|-------|--------|-----------|---------|
| `_Repo: {repo-name}_` | Non-empty string | Must match a repo ID in coordination-manifest.json | Target repo for sub-spec creation |
| `_SubSpec: {spec-name}_` | Kebab-case, non-empty | Must be valid kebab-case identifier | Sub-spec name created in target repo |
| `_DependsOn: {task-ids}_` | Comma-separated task IDs | All referenced IDs must exist in the task list | Cross-task dependency ordering |
