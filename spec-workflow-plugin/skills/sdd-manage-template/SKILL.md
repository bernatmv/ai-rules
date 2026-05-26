---
name: sdd-manage-template
description: Lists, previews, customizes, validates, resets, diffs, and syncs SDD
  templates. Use when asked to list templates, show a template, customize a template,
  validate templates, reset a template, diff templates, or sync template defaults.
allowed-tools: Read Write Edit Bash Agent AskQuestion AskUserQuestion TaskCreate TaskUpdate WebFetch
metadata:
  version: 3.3.1
  category: workflow
  dependencies: [sdd-common]
  author: membership-platforms-sdd-guild
---

> **Paths:** See `$SKILLS/sdd-common/references/path-conventions.md`. Scripts: `.spec-workflow/sdd {group}/{script}.py`.

# SDD: Manage Templates

Manages the template lifecycle for spec and steering documents.

## Contents

- [Dependencies](#dependencies)
- [Invocation Examples](#invocation-examples)
- [Workflow](#workflow)
- [Workflow Progress](#workflow-progress)
- [Safety Rules](#safety-rules)
- [Edge Cases](#edge-cases)
- [Completion](#completion)
- [Reference Files](#reference-files)

## Dependencies

> **Load on demand**: Read each file only when the workflow reaches that step — not all upfront.

| Step | File | Kind | Freedom |
|------|------|------|:-:|
| All | `$SKILLS/sdd-common/scripts/sdd_core/templates.py` | read | M |
| All | `$SKILLS/sdd-common/references/state-scope.md` (scope + lifetime of persisted state) | read | L |
| All | `$SKILLS/sdd-common/scripts/util/manage-template.py` | run | L |
| Validation | `$SKILLS/sdd-common/references/template-compliance.md` | read | M |
| Health | `$SKILLS/sdd-common/references/pre-flight-protocol.md` | read | L |
| Health | `$SKILLS/sdd-common/scripts/workspace/check-health.py` | run | L |
| Bug-fix fallback | `$SKILLS/sdd-create-spec/references/bug-fix-templates.md` | read | M |

## Invocation Examples

| Request | Action |
|---------|--------|
| "sdd list templates" | Show all templates with status |
| "sdd show template requirements" | Display resolved requirements template |
| "sdd customize template design" | Copy default design template to user-templates for editing |
| "sdd validate template tasks" | Validate user tasks template |
| "sdd validate templates" | Validate all user-templates |
| "sdd reset template tech" | Remove tech user-template override |
| "sdd diff template requirements" | Diff user vs default requirements template |
| "sdd sync templates" | Re-copy reference templates to workspace defaults |
| "sdd check workspace health" | Run health check, report status |
| "sdd manage-template health" | Same — via manage-template entry point |

## Workflow

### Step 1: Resolve Command

Parse user request to determine subcommand and template type.
Valid types: run `.spec-workflow/sdd util/manage-template.py list` to enumerate (canonical list in
`sdd_core/templates.py:ALL_TEMPLATE_TYPES`).

### Step 2: Execute

Run `.spec-workflow/sdd util/manage-template.py {subcommand} {type}`.
Present output to user.

For `customize`: after copy, remind user to edit the file. After edit,
auto-run `validate`. If errors found, show errors with fix suggestions and
prompt user to re-edit. Repeat validate-fix cycle until valid or user
explicitly skips.

For `reset`: require confirmation before deletion.

For `sync`: report which templates were written to `.spec-workflow/templates/`.

**Plan-validate-apply (opt-in, auditable alternative to `customize`/`reset`/`sync`):**

Use this form when a reviewer wants to see exactly which files a
template operation will touch before any bytes are written.

```bash
.spec-workflow/sdd util/manage-template.py plan {type} --action customize \
  --out /tmp/template-plan.json
.spec-workflow/sdd util/manage-template.py validate-plan /tmp/template-plan.json
.spec-workflow/sdd util/manage-template.py apply-plan /tmp/template-plan.json
```

`plan` emits a `template-plan.json` (schema version is embedded).
`validate-plan` fails with actionable errors if the target already exists
or the default template is missing. `apply-plan` re-runs validation and
then executes the plan atomically.

### Step 2.1: Health (when subcommand is `health`)

Run `.spec-workflow/sdd util/manage-template.py health [--auto-fix]`.
Present results to user. If unhealthy, offer `--auto-fix`. After auto-fix,
re-present updated status.

### Step 3: Follow-Up

Report results. Suggest next action per `$SKILLS/sdd-common/references/workflow-handoffs.md`.

## Workflow Progress

Copy this checklist and track progress:

```
- [ ] Step 1: Resolve command — parse subcommand + template type — Triage: T0
- [ ] Step 2: Execute — run `.spec-workflow/sdd util/manage-template.py {subcommand} {type}`
  - → If `customize`: validate-fix feedback loop
  - → If `reset`: confirmation prompt (Triage: T1)
  - → If `health`: report status, offer `--auto-fix` if unhealthy (Step 2.1)
- [ ] Step 3: Follow-up — report results, suggest next action
```

## Safety Rules

See `$SKILLS/sdd-common/references/safety-rules.md`.
- Never overwrite user-templates without explicit confirmation
- `reset` requires confirmation prompt
- `sync` only modifies `.spec-workflow/templates/`, never `user-templates/`

## Edge Cases

| Situation | Action |
|-----------|--------|
| Workspace not initialized | Run pre-flight per `$SKILLS/sdd-common/references/pre-flight-protocol.md` |
| User-template already exists on customize | Report exists, suggest edit or reset |
| Validate finds errors | Show errors with fix suggestions; prompt re-edit |
| Bug-fix template type not found | Fall back to reference in `$SKILLS/sdd-create-spec/references/bug-fix-templates.md` |
| No user-templates exist for diff/validate/reset | Report "no custom templates found" |
| Reference templates missing (broken install) | Error with hint to reinstall skills |

## Completion

Template operation complete.

## Reference Files

- Template catalog: references/template-catalog.md
- Template compliance: $SKILLS/sdd-common/references/template-compliance.md
- Script conventions: $SKILLS/sdd-common/references/script-conventions.md
