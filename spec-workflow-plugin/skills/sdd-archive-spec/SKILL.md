---
name: sdd-archive-spec
description: Archives completed or abandoned specs by moving them to the archive directory
  with metadata. Supports listing archived specs for reference. Use when asked to
  archive a spec, archive all completed specs, or list archived specs.
allowed-tools: Read Write Edit Bash Agent AskQuestion AskUserQuestion TaskCreate TaskUpdate WebFetch
metadata:
  version: 3.3.1
  category: workflow
  dependencies: [sdd-common]
  author: membership-platforms-sdd-guild
---

> **Paths:** See `$SKILLS/sdd-common/references/path-conventions.md`. Scripts: `.spec-workflow/sdd {group}/{script}.py`.

# SDD: Archive Spec

Archives completed or abandoned specs by moving them from `.spec-workflow/specs/{spec-name}/` to `.spec-workflow/archive/specs/{spec-name}/` with an archive metadata file. Preserves all spec documents and implementation logs for future reference.

## Contents

- [Dependencies](#dependencies)
- [Invocation Examples](#invocation-examples)
- [Workflow](#workflow)
- [List Archived Specs](#list-archived-specs)
- [Workflow Progress](#workflow-progress)
- [Safety Rules](#safety-rules)
- [Edge Cases](#edge-cases)
- [Completion](#completion)
- [Reference Files](#reference-files)

## Dependencies

> Load each file only when the workflow reaches that step. Freedom legend: see `$SKILLS/sdd-common/references/freedom-column.md`.

| Step | File | Kind | Freedom |
|------|------|------|:-:|
| Step 1 | `$SKILLS/sdd-common/references/tool-patterns.md` | read | L |
| Step 1 | `$SKILLS/sdd-common/scripts/spec/check-status.py` | run | L |
| Step 2 | `$SKILLS/sdd-common/references/prompt-conventions.md` | read | L |
| Step 2 | `$SKILLS/sdd-common/scripts/util/generate-prompt.py` (prompt access) | run | L |
| Step 3 | `$SKILLS/sdd-common/scripts/spec/archive.py` | run | L |
| Edge cases | `$SKILLS/sdd-common/references/common-edge-cases.md` | read | M |
| All | `$SKILLS/sdd-common/references/state-scope.md` (scope + lifetime of persisted state) | read | L |

## Invocation Examples

| Request | Action |
|---------|--------|
| "sdd archive [name]" | Archive a completed spec |
| "sdd archive all" | Archive all completed specs |
| "sdd list archived" | Show archived specs |

## Workflow

### Step 1: Check Spec Status

Verify the spec exists and assess its state.

```
.spec-workflow/sdd spec/check-status.py --spec-name "{spec-name}"
```

| Status | Action |
|--------|--------|
| All tasks `[x]` | Safe to archive — proceed |
| Some tasks incomplete | Present `archive-incomplete` prompt from registry via AskQuestion |
| No tasks.md | Present `archive-incomplete` prompt from registry via AskQuestion |
| Pending approvals | Present `archive-incomplete` prompt from registry via AskQuestion |
| Spec not found | Report error: "Spec '{name}' not found. Available specs: ..." |

Invocation for the `archive-incomplete` prompt:

```
.spec-workflow/sdd util/generate-prompt.py --type archive-incomplete
```

### Step 2: Confirm with User

Present archive summary:

```markdown
## Archive Summary

| Field | Value |
|-------|-------|
| Spec | {spec-name} |
| Status | {completed/incomplete/no-tasks} |
| Documents | {list of .md files} |
| Implementation Logs | {count} entries |
| Pending Approvals | {count} |
```

Present the `archive-confirm` prompt from the registry with params
`spec_name={spec-name}`:

```
.spec-workflow/sdd util/generate-prompt.py --type archive-confirm --params spec_name=<value>
```

See `$SKILLS/sdd-common/references/prompt-conventions.md` § Integration Pattern.

**NEVER archive without explicit user confirmation.**

### Step 3: Execute Archive

Run the archive script:

```
.spec-workflow/sdd spec/archive.py --spec-name "{spec-name}" --action archive
```

The script atomically moves all files from `.spec-workflow/specs/{spec-name}/` to `.spec-workflow/archive/specs/{spec-name}/`.

After the move, create archive metadata file `.spec-workflow/archive/specs/{spec-name}/_archive-meta.md`:

```markdown
# Archive Metadata

- **Spec**: {spec-name}
- **Archived**: {ISO timestamp}
- **Status at archive**: {completed/incomplete/abandoned}
- **Tasks completed**: {x}/{total}
- **Reason**: {user-provided or "Completed"}
```

Clean up any orphaned approval files in `.spec-workflow/approvals/{spec-name}/`.

### Step 4: Report Results

```markdown
## Archive Complete

Spec `{spec-name}` archived to `.spec-workflow/archive/specs/{spec-name}/`.

| Item | Result |
|------|--------|
| Documents moved | {count} |
| Implementation logs moved | {count} |
| Approvals cleaned | {count} |
| Original directory removed | Yes |
```

Spec archived.

## List Archived Specs

When user asks to list archived specs, scan `.spec-workflow/archive/` and present:

```markdown
## Archived Specs

| Spec | Archived Date | Status | Tasks |
|------|--------------|--------|-------|
| {name} | {date} | {status} | {x}/{total} |
```

Read `_archive-meta.md` from each archive directory for metadata. If the archive directory is empty, report "No archived specs found."

## Workflow Progress

Copy this checklist and track progress:

```
- [ ] Step 1: Check spec status — Triage: T0
- [ ] Step 2: Confirm with user
- [ ] Step 3: Execute archive
- [ ] Step 4: Report results
```

## Safety Rules

See `$SKILLS/sdd-common/references/safety-rules.md`. Key rules for this skill: Never archive without explicit user confirmation; preserve all documents and logs during archive.

## Edge Cases

See `$SKILLS/sdd-common/references/common-edge-cases.md` for shared patterns (Spec Not Found). Skill-specific edge cases:

| Situation | Action |
|-----------|--------|
| Archive directory already exists | Prompt: overwrite or cancel |
| Move fails (permissions) | Report error, suggest manual move |
| User cancels | Report "Archive cancelled" and stop |
| Batch archive | Present `batch-archive` prompt from registry via AskQuestion |
| Spec has pending approvals | Warn about orphaned approvals, clean up if user confirms |
| Archive directory doesn't exist | Create `.spec-workflow/archive/` automatically |

Invocation for the `batch-archive` prompt:

```
.spec-workflow/sdd util/generate-prompt.py --type batch-archive
```

## Completion

Archive operation complete. To check remaining specs, run `sdd status`.

## Reference Files

- Common edge cases: $SKILLS/sdd-common/references/common-edge-cases.md
- Script: $SKILLS/sdd-common/scripts/spec/check-status.py
- Script: $SKILLS/sdd-common/scripts/spec/archive.py
- Prompt access: `$SKILLS/sdd-common/scripts/util/generate-prompt.py` (do NOT read `prompt-registry.json` directly)
