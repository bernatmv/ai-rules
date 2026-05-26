# Implementation Telemetry Logging

Shared reference for skills that call `log-implementation` (`sdd-implement-spec`, `sdd-review-code`).


## Contents

- [Workflow Sequence](#workflow-sequence)
- [Pre-Implementation: Search Existing Logs](#pre-implementation-search-existing-logs)
- [Log the Implementation](#log-the-implementation)
- [Artifact Field Reference](#artifact-field-reference)

## Workflow Sequence

Follow this sequence for each task (see `task-execution-loop.md` for the full per-task procedure):

1. **Mark in-progress:** `impl/advance-task.py --target {spec-name} --task-id {id} --action start`
2. **Search existing logs:** Search `.spec-workflow/specs/{spec-name}/Implementation Logs/` for existing artifacts to reuse (see search guidance below)
3. **Implement:** Write the code following task guidance
4. **Log implementation:** Call `util/log-implementation.py` with detailed artifacts (see below)
5. **Mark complete:** `impl/advance-task.py --target {spec-name} --task-id {id} --action finish --log-id {id}`

> **Canonical suffix:** The exact wording embedded in `_Prompt` fields is defined in
> `$SKILLS/sdd-common/references/prompt-suffix-canonical.md`. The validation script
> (`../scripts/spec/lint-tasks.py`) checks compliance.

## Pre-Implementation: Search Existing Logs

Before implementing, search for existing artifacts to prevent duplication:

```bash
# Search within this spec's logs
rg "keyword" ".spec-workflow/specs/{specName}/Implementation Logs/"

# Search across ALL specs (for shared code discovery)
rg "keyword" ".spec-workflow/specs/*/Implementation Logs/"
```

**What to search for:**
- API endpoint paths (e.g., `/api/users`)
- Component names (e.g., `UserProfile`)
- Function/class names that might already exist
- Integration patterns between frontend and backend

If existing code matches what the task requires, **leverage it** instead of reimplementing.

> **Reading existing logs.** Use grep/Read on `.spec-workflow/specs/{spec-name}/Implementation Logs/*.md` to search and read logs. Log files are named `task-{id}_{timestamp}_{uuid}.md`.

## Log the Implementation

> **⚠️ Artifacts are REQUIRED.** The `log-implementation` tool rejects calls with empty or missing `artifacts`. You must include at least one non-empty artifact type array (`apiEndpoints`, `components`, `functions`, `classes`, or `integrations`). This data prevents code duplication by future agents.

```
.spec-workflow/sdd util/log-implementation.py \
  --spec-name "{spec-name}" \
  --task-id "{task-id}" \
  --summary "{description of what was implemented}" \
  --files-modified '["path/to/modified.ts", "path/to/other.ts"]' \
  --files-created '["path/to/new.ts"]' \
  --statistics '{"linesAdded": 150, "linesRemoved": 10}' \
  --artifacts '{ ... }'
```

All collection/object arguments (`--files-modified`, `--files-created`, `--statistics`, `--artifacts`) accept **JSON strings**. There are no `--lines-added` or `--lines-removed` flags — pass line counts inside `--statistics`.

> `statistics.preExisting`: `true` when the *production* code targeted by this task already existed. Test files created during verification do not change this flag.

> `statistics.filesChanged` is auto-calculated from `filesModified` + `filesCreated` lengths. Do not include it in the input.

## Artifact Field Reference

| Type | Required Fields | Optional Fields |
|------|----------------|-----------------|
| `apiEndpoints[]` | method, path, purpose, location | requestFormat, responseFormat |
| `components[]` | name, type, purpose, location | props, exports |
| `functions[]` | name, purpose, location, isExported | signature |
| `classes[]` | name, purpose, location, isExported | methods |
| `integrations[]` | description, frontendComponent, backendEndpoint, dataFlow | — |
| `verifications[]` | description, scope, result | location |
