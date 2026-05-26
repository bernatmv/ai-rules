# Approval Flow

> **Related protocols:** Called from SKILL.md Dependencies tables (never via chain).
> Uses: `prompt-conventions.md` (prompt generation patterns).
> Part of: `review-approval-pipeline.md` pipeline (Step 3: Approve).

Unified approval reference for all SDD skills.

> **Human-actor ceremony.** Approve transitions are gated by H1; see [`human-approval-ceremony.md` § Retry On H1 Rejection](human-approval-ceremony.md#retry-on-h1-rejection) for the canonical retry shim (rendered by `sdd_core.command_templates.approve_with_human_env`) and the `SDD_HUMAN_APPROVAL=1` env marker.

## Contents
- [Category Conventions](#category-conventions)
- [Pattern A: Inline Confirm](#pattern-a-inline-confirm)
- [Pattern B: Formal Approval](#pattern-b-formal-approval)
- [Approval Decision Matrix](#approval-decision-matrix)
- [Resilient Steering Approval Discovery](#resilient-steering-approval-discovery)
- [Audit Logging](#audit-logging)
- [Iteration Limit](#iteration-limit)
- [Revision Workflow](#revision-workflow)

## Category Conventions

When calling approval scripts, the `categoryName` parameter determines storage:

| Document Type | `category` | `categoryName` | Storage Path |
|--------------|-----------|----------------|--------------|
| Spec document | `"spec"` | Spec name in kebab-case (e.g., `"user-auth"`) | `approvals/{spec-name}/` |
| Steering document | `"steering"` | `"steering"` (literal string, always) | `approvals/steering/` |
| Discovery artifact | `"discovery"` | Discovery project name in kebab-case (e.g., `"user-onboarding"`) | `approvals/{project-name}/` |

All three steering documents (product.md, tech.md, structure.md) **must** use `categoryName: "steering"`.

## Pattern A: Inline Confirm

Low-ceremony approval scripts (request → approve → delete) used as the execution mechanism for `approval-formal` / `approval-formal-required` prompt outcomes in update and creation workflows, and directly for task refresh confirmation.

1. Agent presents document/changes
2. One prompt:

Present the `approval-inline` prompt from the registry with params:
`doc={doc}`. See `prompt-conventions.md` § Integration Pattern.

3. If reject: one free-text prompt for reason → agent records in audit log
4. Agent calls `.spec-workflow/sdd approval/request.py` + `.spec-workflow/sdd approval/update-status.py` + `.spec-workflow/sdd approval/delete.py` in sequence

```
.spec-workflow/sdd approval/request.py --target-name "{categoryName}" \
  --title "{title}" --file-paths "{path}" \
  --type document --category {category}
```
Extract `approvalId` and `approvalFilePath` from the output. The approval file
is created at `.spec-workflow/approvals/{categoryName}/{approvalId}.json`. Use
`approvalFilePath` as `{source_file}` in subsequent `update-status.py` and
`delete.py` calls. Then:
```
.spec-workflow/sdd approval/update-status.py \
  "{source_file}" "{action: approve|reject|needs_revision}" "{response}" --actor "{actor}"
```
Then delete:
```
.spec-workflow/sdd approval/delete.py --approval-id "{approvalId}"
```

**No separate manage-status session needed.**

## Pattern B: Formal Approval

High-ceremony approval for: spec phase approvals (requirements.md, design.md, tasks.md) during creation, steering doc creation, and standalone `sdd-manage-status` operations.

1. Agent presents document summary
2. One prompt:

Present the `approval-formal` prompt from the registry with params:
`doc={doc}`. See `prompt-conventions.md` § Integration Pattern.

3. Handle response:
   - **Approve (default)**: `.spec-workflow/sdd approval/update-status.py` with "Approved via agent"
   - **Approve with comment**: free-text for comment, then update
   - **Needs revision**: free-text for feedback → agent revises → re-presents (max 3 cycles)
   - **Skip for now**: agent pauses, can resume later

4. Use the `approval_commands` dict emitted by `pipeline-tick.py --phase pre-approval` — it contains the three canonical CLI shapes (request / update_status / delete) with `{approvalId}` and `{approvalFilePath}` placeholders and a `placeholder_substitution_note`. Do not hand-craft these commands.

Concrete example (after `pipeline-tick --phase pre-approval` returns):

```
.spec-workflow/sdd approval/request.py --target-name "my-feature" \
  --title "Spec: my-feature" --file-paths ".spec-workflow/specs/my-feature/requirements.md" \
  --type document --category spec

.spec-workflow/sdd approval/update-status.py \
  {approvalFilePath} {action} {response}

.spec-workflow/sdd approval/delete.py --approval-id {approvalId}
```

**Creation skills handle Pattern B inline.** `sdd-manage-status` remains the dedicated skill for standalone formal approvals.

## Approval Decision Matrix

In creation workflows, Pattern B is invoked via the Review and Approval Pipeline
(`review-approval-pipeline.md`), not directly by skills.

| Context | Mechanism | Rationale |
|---------|-----------|-----------|
| Steering per-doc creation | Pipeline (`per-document`) | Consistent validation + optional review |
| Steering final | Pipeline (`final`) | Cross-doc consistency + package-level gate |
| Steering update | Pipeline (`final`) via update-mode-workflow | User must consent |
| Spec per-doc creation (sequential) | Pipeline (`per-document`) | Consistent validation + optional review |
| Spec batch approval | `spec-batch-approval` prompt (unchanged) | Self-contained batch flow |
| Spec final | Pipeline (`final`) | Cross-doc consistency + package-level gate |
| Spec update | Pipeline (`final`) via update-mode-workflow | User must consent |
| Task refresh | Pattern A (unchanged) | User already reviewed diff |
| Standalone `sdd approve` | Pattern B (unchanged) | Explicit formal approval intent |

## Resilient Steering Approval Discovery

When scanning for steering approvals, do not rely on the directory name alone:

1. Scan **all** subdirectories under `.spec-workflow/approvals/`
2. Read each `.json` file and check the `category` field
3. Include any file where `"category": "steering"`, regardless of which subdirectory it is in
4. If found outside `approvals/steering/`, flag it as misplaced in the results

## Dual-Ledger Semantics

Approval state is recorded in two ledgers:

1. **Snapshot/active ledger** — the canonical source of truth. `approvals/{categoryName}/{approval-id}.json` holds the current approval record and the matching `.snapshots/{basename}/metadata.json` rotation. `has_approved` and `has_approved_snapshot` consult this layer.
2. **Audit ledger** — `.spec-workflow/approval-audit.log` mirrors every approval status transition as an immutable JSONL row (channel `approval`). Entries carry `newStatus`, `filePath`, `categoryName`, and `approvalId`.

Most call sites read only the snapshot/active layer because it carries the full identity tuple (canonical path + content hash). The audit log is consulted opportunistically: `spec/check-status.py --include-audit-log` and `has_approved_audit` answer "did this phase ever clear?" even when the snapshot directory was rotated or the active record was retired. The default off setting preserves backwards compatibility — enabling the flag never weakens the gate, only widens what counts as "approved" for read-only status surfaces.

## Audit Logging

For approval actions that write to the `response` field in approval JSON or audit log, fold the default comment into the action choice itself. Do NOT use a separate prompt round for comment collection.

When the action includes a default comment (e.g., approve), embed it in the option label:
- `"Approve (comment: 'Approved via agent')"`
- `"Approve — I'll provide a comment"`

When the user selects a custom-comment or reject/needs_revision option, prompt conversationally ("Please enter your comment:") and read their next chat message. Pass it as the `response` arg to `.spec-workflow/sdd approval/update-status.py`.

## Iteration Limit

After 3 revision cycles without approval, escalate to user.

## Revision Workflow

To reset an approval cycle:
1. Delete the resolved approval: `.spec-workflow/sdd approval/delete.py --approval-id {id}`
2. Make document changes
3. Request new approval: `.spec-workflow/sdd approval/request.py ...`
