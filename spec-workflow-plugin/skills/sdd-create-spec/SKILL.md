---
name: sdd-create-spec
description: Creates spec documents (requirements.md, ui-design.md, design.md, tasks.md) through a phased workflow with template-guided authoring and approval gates. Supports both standard feature specs and bug-fix specs with auto-detected mode. Use when asked to create a spec, resume a spec, update a spec, bug fix, or hotfix.
allowed-tools: Read Write Edit Bash Agent AskQuestion AskUserQuestion TaskCreate TaskUpdate WebFetch
metadata:
  version: 3.3.1
  category: development
  dependencies: [sdd-common, sdd-review-spec-docs, sdd-manage-status]
  author: membership-platforms-sdd-guild
---

> **Paths:** See `$SKILLS/sdd-common/references/path-conventions.md`. Scripts: `.spec-workflow/sdd {group}/{script}.py`.

# SDD: Create Spec

Stepped workflow: Requirements → UI Design (optional) → Design → Tasks → Implementation. Two modes auto-detected from spec name + request (see `$SKILLS/sdd-common/references/detection-rules.md`).

| Mode | Trigger | Templates | Extra Steps |
|------|---------|-----------|-------------|
| **Standard** | Default | `spec-workflow.md` | — |
| **Bug Fix** | `fix-*` prefix or keywords: bug / fix / hotfix / patch | `bug-fix-templates.md` | Triage (Step 0), fast path for Critical/High |

## Contents

- [Dependencies](#dependencies)
- [Invocation Examples](#invocation-examples)
- [Mode Detection](#mode-detection)
- [Naming Convention](#naming-convention)
- [Approval Modes](#approval-modes)
- [Pipeline Parameters](#pipeline-parameters)
- [Workflow](#workflow)
- [Workflow Progress](#workflow-progress)
- [Safety Rules](#safety-rules)
- [Edge Cases](#edge-cases)
- [Completion](#completion)
- [Handoffs](#handoffs)
- [Reference Files](#reference-files)

## Dependencies

> Load each file only when the workflow reaches that step. Freedom legend: see `$SKILLS/sdd-common/references/freedom-column.md`.

| Step | File | Kind | Freedom |
|------|------|------|:-:|
| Mode detection | `$SKILLS/sdd-common/references/tool-patterns.md` | read | M |
| Mode detection | `$SKILLS/sdd-common/scripts/spec/detect-type.py` | run | L |
| Context detection | `$SKILLS/sdd-common/scripts/spec/detect-context.py` | run | L |
| Step 0 | `$SKILLS/sdd-create-spec/references/bug-fix-workflow.md` (bug-fix only) | read | M |
| Step 0 | `$SKILLS/sdd-create-spec/references/triage-criteria.md` (bug-fix only) | read | M |
| Step 1 | `$SKILLS/sdd-common/references/pre-flight-protocol.md` | read | L |
| Step 1 | `$SKILLS/sdd-common/scripts/spec/check-status.py` | run | L |
| Approval modes | `$SKILLS/sdd-create-spec/references/approval-modes.md` | read | M |
| Steps 3/7/9 (standard) | `$SKILLS/sdd-create-spec/references/spec-workflow.md` | read | H |
| Steps 3/7/9 (standard) | `$SKILLS/sdd-common/references/template-compliance.md` | read | M |
| Step 1.1 | `$SKILLS/sdd-common/references/update-mode-user-gathering.md` | read | M |
| Step 1.1 | `$SKILLS/sdd-common/references/update-mode-workflow.md` | read | L |
| Step 3 (requirements) | `$SKILLS/sdd-common/references/requirements-antipatterns.md` | read | M |
| Step 3 (requirements) | Pre-launch-check envelope (`template_resolve_commands.requirements_md` for the write command; envelope `next_action_command_sequence` for the validator) | run | L |
| Step 5 (ui-design) | `$SKILLS/sdd-common/references/template-compliance.md` | read | M |
| Steps 3/7/9 (bug-fix) | `$SKILLS/sdd-create-spec/references/bug-fix-templates.md` | read | M |
| Steps 4/6/8/10/11 | `$SKILLS/sdd-common/references/review-approval-pipeline.md` | read | L |
| Steps 4/6/8/10/11 | `$SKILLS/sdd-common/references/approval-flow.md` (§ Pattern B, § Category Conventions) | read | L |
| Step 9 (tasks) | Pre-launch-check envelope (`template_resolve_commands.tasks_md` for the write command; envelope `next_action_command_sequence` for the validator) | run | L |
| Step 9 (optional — override only) | `$SKILLS/sdd-common/references/prompt-suffix-canonical.md` | read | H |
| Step 10 (tasks) | `$SKILLS/sdd-common/references/task-validation-rules.md` (§ _Requirements: Format) | read | L |
| Step 11 | Hand-off to `$SKILLS/sdd-implement-spec` | read | H |
| Step 1.1 / Steps 4/6/8/10/11 | `$SKILLS/sdd-common/references/harness-task-binding.md` | read | L |
| All | `$SKILLS/sdd-common/references/state-scope.md` (scope + lifetime of persisted state) | read | L |

## Invocation Examples

| Request | Action | Mode |
|---------|--------|------|
| "sdd create spec [name]" | Full spec workflow | Standard |
| "sdd resume spec [name]" | Resume from last incomplete phase | Auto-detect |
| "sdd bug fix [description]" | Bug fix workflow with triage | Bug Fix |
| "sdd hotfix [description]" | Critical/high severity fast path | Bug Fix |
| "sdd update spec [name] [doc]" | Update mode — targeted edit + approval | Auto-detect |

## Mode Detection

Run `.spec-workflow/sdd spec/detect-type.py --target {spec-name}` — `data.type` returns `"bug-fix"` or `"standard"`. A `fix-*` prefix or bug-fix keyword in the request forces bug-fix mode, which enforces `fix-{slug}` naming.

## Naming Convention

Standard: kebab-case (`user-auth`). Bug-fix: `fix-{slug}` (`fix-login-sso-failure`). One spec at a time, path `.spec-workflow/specs/{spec-name}/`.

## Approval Modes

Sequential (default) writes and approves each doc in turn; Batch defers approval to Step 10.1. Auto-detected at Step 1 via `detect-context.py`. See `references/approval-modes.md` for detection rules, single-document mode, and overrides.

## Pipeline Parameters

Approval steps (4, 6, 8, 10, 11) all use `$SKILLS/sdd-common/references/review-approval-pipeline.md`.

**Shared params:** `category: spec`, `target-name: {spec-name}`, `review_skill: sdd-review-spec-docs`, `max_fix_cycles: 2`

| Step | scope | doc | doc_list | title |
|------|-------|-----|----------|-------|
| 4 | `per-document` | requirements.md | `requirements.md` | Requirements: {spec-name} |
| 6 | `per-document` | ui-design.md | `ui-design.md` | UI Design: {spec-name} |
| 8 | `per-document` | design.md | `design.md` | Design: {spec-name} |
| 10 | `per-document` | tasks.md | `tasks.md` | Tasks: {spec-name} |
| 11 | `final` | (all) | `requirements.md, [ui-design.md,] design.md, tasks.md` | Spec: {spec-name} |

## Workflow

### Step 0: Triage (bug-fix mode only)

See `references/bug-fix-workflow.md` § Triage for severity classification and routing. If Critical/High, proceed to Step 0.1.

### Step 0.1: Fast Path (Critical/High bug-fix only)

See `references/bug-fix-workflow.md` § Fast Path. After fast path approval, proceed to Step 9, then Step 11.

### Step 1: Pre-Flight Validation

Run pre-flight per `$SKILLS/sdd-common/references/pre-flight-protocol.md`.
Run `.spec-workflow/sdd spec/check-status.py`, verify directory exists, check name collision, warn if steering docs missing.

```
.spec-workflow/sdd workspace/ensure-healthy.py --workspace .
.spec-workflow/sdd spec/check-status.py --target {spec-name}
```

**Reconcile git-status** — MANDATORY when `ensure-healthy.py` surfaces any git-state advisory **or** a spec directory is listed by `detect-doc-state.py` but missing on disk (phantom). Surface the returned `banner` verbatim to the user:
```
.spec-workflow/sdd spec/check-status.py --reconcile-git-status --workspace .
```

**Document state detection** — runs automatically on every `--phase launch` (see `$SKILLS/sdd-common/references/review-approval-pipeline.md` § Launch precondition recovery — `next_action_sequence`). Recommended Step 1 call for the initial status check (consume `summary.missing_required` + `user_gathering.required` before routing):
```
.spec-workflow/sdd util/detect-doc-state.py --category spec --target-name {spec-name} --workspace .
```

**Detect approval mode** (see § Approval Modes above):
```
.spec-workflow/sdd spec/detect-context.py --target {spec-name} \
  [--workspace {path}]
```
Read the `approvalMode` field from the output. If `batch`, Steps 4/6/8/10 are skipped and Step 10.1 is used instead.

| Check | Routing |
|-------|---------|
| Spec doesn't exist | Proceed to creation (Step 2+) |
| Spec exists + user wants full regeneration | **Prompt:** (a) Resume existing spec (b) Choose new name (c) Overwrite existing |
| Spec exists + user wants targeted edit | Route to Step 1.1 (update mode) |

**Resume routing** (when resuming an existing spec): see `references/spec-workflow.md` § Resume for the `currentPhase` → step table.

### Step 1.1: Update Mode (Targeted Edit)

**Triggered when**: Spec exists AND user requests a specific change (not full regeneration).

**`user_gathering.required` in update mode.** Apply the routing table
in `$SKILLS/sdd-common/references/update-mode-user-gathering.md`
(§ Update-mode override). The reference owns the rule so creation-mode
and update-mode branches stay aligned in a single place.

Follow `$SKILLS/sdd-common/references/update-mode-workflow.md` with:

| Param | Value |
|-------|-------|
| doc-root | `.spec-workflow/specs/{spec-name}/` |
| review skill | `sdd-review-spec-docs` |
| approval category | spec |
| target-name | {spec-name} |
| downstream rules | See table below |
| thought-partner | `required-with-triage` |
| thought-partner-questions | See `references/spec-workflow.md` § Update Mode Exploration |
| thought-partner-depth | `full` for requirements.md, ui-design.md; `light` for design.md, tasks.md |

**Downstream impact rules:**

| Document Changed | Downstream Warning |
|------------------|--------------------|
| requirements.md | "UI design, design, and tasks may need updates. Run `sdd review spec {name}` after approval." |
| ui-design.md | "Design may need updates to reflect UI changes. Run `sdd review spec {name}` after approval." |
| design.md | "Tasks may need refresh. Run `sdd refresh tasks {name}` after approval." |
| tasks.md | No downstream impact. |

**Mandatory entry call** (before Step 1). Run exactly this command. Do not improvise — the launch phase uses a different envelope and will block:

```
.spec-workflow/sdd review/pipeline-tick.py --category spec --target-name "{spec-name}" --phase update-launch -- --doc-list "{doc_list}" --scope per-document --workflow-mode update
```

The envelope's `progress_checklist` (key `update-mode.default.v1`)
binds Steps 4 / 6 / 7.1 / 8. Pass `todo_write_payload` directly to
TodoWrite.

If you accidentally invoke `--phase launch --workflow-mode update --scope per-document` against a spec whose required docs already exist, the dispatcher blocks with `outcome: "preflight_required"` and advisory `wrong_update_entry_phase`; copy the advisory's `next_action_command` (which matches the literal above).

### Step 2: Read Steering Docs + PRD

Load `.spec-workflow/steering/{tech,structure,product}.md` if present (warn if missing) plus `.spec-workflow/discovery/{spec-name}/prd.md` when it exists.

### Step 3: Write requirements.md

Run the pre-launch-check command from `template_resolve_commands.requirements_md` and consume the envelope per `$SKILLS/sdd-common/references/tool-patterns.md § Pre-Launch Envelope Contract`. Loop write ↔ validate until `ok: true`; on `repeat_detected: true`, escalate via the returned `ask_question_payload`.

**Pre-launch-check outcome enum** (read `data.outcome`, not `data.ok`): `passed` (validator ran clean — `ok: true`), `not_yet_authored` (validator registered, doc missing — `ok: null`, write the template then retry), `validator_not_registered` (no validator for the doc kind — `ok: null`, just emits `template_resolve_commands`), `lint_failed` (doc exists with findings — `ok: false`, fix and retry).

**Bug-fix mode:** substitute `--doc requirements.md` with `--doc bug-fix-requirements.md`; otherwise same loop plus `bug-fix-templates.md § requirements.md Self-Check` before Step 4.

On any blocked/pending-calls response, follow `$SKILLS/sdd-common/references/review-approval-pipeline.md` § Pending Tool Calls Enforcement (covers `required_tool_calls` ordering and `next_action_sequence` recovery).

### Step 4: Review and Approval for requirements.md

> **Batch mode:** Skip — deferred to Step 10.1.

> **First approval only:** Read `$SKILLS/sdd-common/references/approval-flow.md` § Pattern B for the approval lifecycle (request → update → delete) and § Category Conventions for the storage path. Same pattern applies to Steps 6, 8, 10, 11.

Run the Review and Approval Pipeline per `$SKILLS/sdd-common/references/review-approval-pipeline.md`. See § Pipeline Parameters (Step 4 row).

### Step 5: UI Design Gate (optional)

Always ask the user whether this spec includes UI/UX changes — never skip, even on resume.

| Option | Action |
|--------|--------|
| **Yes — include UI Design** | Pre-work checklist, then write `ui-design.md` |
| **No — skip UI Design** | Jump to Step 7 |

Follow `references/spec-workflow.md` § Steps 5–6 for the pre-work checklist (Figma, design references, pause option), template resolution, and writing procedure.

`ui-design.md` (UI/UX layout, components, interactions) is separate from `design.md` (technical architecture — Step 7).

### Step 6: Review and Approval for ui-design.md

> **Batch mode:** Skip — deferred to Step 10.1.

Applies only when ui-design.md was created in Step 5. Run the pipeline per `$SKILLS/sdd-common/references/review-approval-pipeline.md`. See § Pipeline Parameters (Step 6).

### Step 7: Write design.md

- **Standard:** Codebase analysis, resolve + substitute per `$SKILLS/sdd-common/references/template-compliance.md`, write per `spec-workflow.md` § Steps 7–8.
- **Bug-fix:** Resolve `bug-fix-design` template per `template-compliance.md` (fall back to `bug-fix-templates.md` § Fix Design Template), run Self-Check, then Step 8.

### Step 8: Review and Approval for design.md

> **Batch mode:** Skip — deferred to Step 10.1.

Run the pipeline per `$SKILLS/sdd-common/references/review-approval-pipeline.md`. See § Pipeline Parameters (Step 8).

### Step 9: Write tasks.md

Run the pre-launch-check command from `template_resolve_commands.tasks_md` and consume the envelope per `$SKILLS/sdd-common/references/tool-patterns.md § Pre-Launch Envelope Contract`. Execute `template_resolve_commands.tasks_md` verbatim (it substitutes `{spec_name}`, the 4-step lifecycle suffix, and the `Implement the task for spec …:` prefix — owner: `sdd_core.task_prompts`), then draft. Override only via `$SKILLS/sdd-common/references/prompt-suffix-canonical.md`. Bug-fix mode: substitute `--doc tasks.md` with `--doc bug-fix-tasks.md` (2-4 tasks + `bug-fix-templates.md § Fix Tasks Self-Check`).

### Step 10: Review and Approval for tasks.md

> **Batch mode:** Skip — deferred to Step 10.1.

Run the pipeline per `$SKILLS/sdd-common/references/review-approval-pipeline.md`. See § Pipeline Parameters (Step 10). Copy the validate invocations verbatim (substitute only `{spec-name}`):
```
.spec-workflow/sdd spec/lint-tasks.py --target {spec-name} --workspace .
.spec-workflow/sdd spec/check-traceability.py --target {spec-name} --workspace .
```
`_Requirements:` accepts numeric refs only (see `$SKILLS/sdd-common/references/task-validation-rules.md § _Requirements: Format`).

### Step 10.1: Batch Approval (batch mode only)

> **Sequential mode:** Skip — per-doc approvals were handled in Steps 4/6/8/10.

Present the `spec-create-batch-approval` prompt with `spec_name="{spec-name}"` and an R/U/D/T summary. See `$SKILLS/sdd-common/references/prompt-conventions.md` § Integration Pattern.

| Option | Action |
|--------|--------|
| Approve all | `.spec-workflow/sdd approval/request.py` → `.spec-workflow/sdd approval/update-status.py` → `.spec-workflow/sdd approval/delete.py` per doc → Step 11 |
| Review individual | Present each doc → return to prompt |
| Needs revision | Collect feedback → revise → re-present |
| Skip | Record pending, exit |

### Step 11: Final Review and Approval

Run the pipeline per `$SKILLS/sdd-common/references/review-approval-pipeline.md` (§ Pipeline Parameters, Step 11). Completion handoff is rendered by the Completion section below.

## Workflow Progress

**Step continuation applies** — see `$SKILLS/sdd-common/references/safety-rules.md` § Workflow Safety.

**Review gate pattern:** see `$SKILLS/sdd-common/references/review-gate-pattern.md` (validate → review gate → approval, session modes, fix-loop TODOs).

Example launch (Step 4):
```
.spec-workflow/sdd review/pipeline-tick.py --category spec --target-name "{spec-name}" \
  --phase launch --review-skill sdd-review-spec-docs \
  --workspace . --doc-list "requirements.md" \
  --scope per-document --workflow-mode create \
  --parent-todo step4 --gate-id step4
```

Track progress against the canonical `progress_checklist` emitted by `--phase launch` (key: `review-gate.default.v1`). The pipeline emits `owned_todo_ids` (and `displaces_todo_id_hints`) on every launch — do not pre-author `stepN` or `approve-*` trackers; the pipeline's IDs are the single source of truth. The step list here is a human-only outline — mandatory order is enforced by the pipeline.

## Safety Rules

See `$SKILLS/sdd-common/references/safety-rules.md`. Key rules: sequential steps (requirements → ui-design → design → tasks), one spec at a time, `per-document` Review and Approval Pipeline at every approval step.

## Edge Cases

Shared patterns live in `$SKILLS/sdd-common/references/common-edge-cases.md` (Template Missing, Approval Rejected, Spec Not Found, Resume, Bug-Fix Detection). Skill-specific:

| Situation | Action |
|-----------|--------|
| No explicit kebab-case name provided | MANDATORY: run `.spec-workflow/sdd spec/check-status.py --suggest-name "{free-text request}"` and feed the returned `ask_question_payload` directly into `AskQuestion`. Do not fabricate candidates. |
| Name collision | Present `spec-collision` prompt from registry via AskQuestion |
| Steering docs missing | Warn, proceed — component identification may be imprecise |
| User changes severity mid-workflow (bug-fix) | Re-evaluate routing |
| Insufficient reproduction info (bug-fix) | Ask clarifying questions (free-text) |
| Targeted edit to non-existent doc within existing spec | Fall back to creation mode for that doc phase |
| Update to design.md with approved tasks | Warn: tasks were approved against the previous design — consider refreshing after approval. |
| Update to requirements.md with approved design | Warn: design was approved against the previous requirements — review alignment. |
| Single-document request (e.g. "requirements.md only") | Run that write step and its approval, then stop. Step continuation still applies within the write-approve pair — approval is never skipped. |

Invocation for the `spec-collision` prompt:

```
.spec-workflow/sdd util/generate-prompt.py --type spec-collision
```

## Completion

Spec creation complete. Suggest next: `.spec-workflow/sdd review/pipeline-tick.py --phase pre-approval ...` then `/sdd-implement-spec {spec-name}`.

## Handoffs

See `references/handoffs.md` (generated from `$SCRIPTS/handoff-registry.json`).
Regenerate via `.spec-workflow/sdd internal_lints/skill_md_handoff_table.py --rewrite`.

## Reference Files

- Standard workflow: $SKILLS/sdd-create-spec/references/spec-workflow.md
- Bug-fix workflow: $SKILLS/sdd-create-spec/references/bug-fix-workflow.md
- Bug-fix templates: $SKILLS/sdd-create-spec/references/bug-fix-templates.md
- Approval modes: $SKILLS/sdd-create-spec/references/approval-modes.md
- Triage criteria: $SKILLS/sdd-create-spec/references/triage-criteria.md
- Handoffs: $SKILLS/sdd-create-spec/references/handoffs.md
- Approval flow: $SKILLS/sdd-common/references/approval-flow.md
- Template compliance: $SKILLS/sdd-common/references/template-compliance.md
- Detection rules: $SKILLS/sdd-common/references/detection-rules.md
