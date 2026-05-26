---
name: sdd-create-steering
description: Creates project steering documents (product.md, tech.md, structure.md)
  through a phased workflow with template-guided authoring and approval gates. Use
  when asked to create steering docs, resume steering docs, or update steering docs.
allowed-tools: Read Write Edit Bash Agent AskQuestion AskUserQuestion TaskCreate TaskUpdate WebFetch
metadata:
  version: 3.3.1
  category: development
  dependencies: [sdd-common, sdd-review-steering-docs, sdd-manage-status]
  author: membership-platforms-sdd-guild
---

> **Paths:** See `$SKILLS/sdd-common/references/path-conventions.md`. Scripts: `.spec-workflow/sdd {group}/{script}.py`.

# SDD: Create Steering Docs

Creates project-level guidance documents when explicitly requested. Steering docs establish vision, architecture, and conventions for established codebases. Three documents are created in sequence: product.md → tech.md → structure.md.

## Contents

- [Dependencies](#dependencies)
- [Invocation Examples](#invocation-examples)
- [Workflow](#workflow)
- [Pipeline Parameters](#pipeline-parameters)
- [Workflow Progress](#workflow-progress)
- [Safety Rules](#safety-rules)
- [Edge Cases](#edge-cases)
- [Completion](#completion)
- [Reference Files](#reference-files)

## Dependencies

> Load each file only when the workflow reaches that step. Freedom legend: see `$SKILLS/sdd-common/references/freedom-column.md`.

| Step | File | Kind | Freedom |
|------|------|------|:-:|
| Step 1 | `$SKILLS/sdd-common/references/tool-patterns.md` | read | M |
| Step 1 | `$SKILLS/sdd-common/references/pre-flight-protocol.md` | read | L |
| Step 1.1 | `$SKILLS/sdd-common/references/prompt-conventions.md` | read | L |
| Steps 2/4/6 | `$SKILLS/sdd-create-steering/references/steering-workflow.md` | read | H |
| Steps 2/4/6 | `$SKILLS/sdd-common/references/template-compliance.md` | read | M |
| Steps 3/5/7/8 | `$SKILLS/sdd-common/references/review-approval-pipeline.md` | read | L |
| All | `$SKILLS/sdd-common/references/approval-flow.md` § Category Conventions (categoryName: "steering") | read | L |
| Steps 3/5/7/8 | `$SKILLS/sdd-common/references/harness-task-binding.md` | read | L |
| Steps 3/5/7/8 | `$SKILLS/sdd-common/references/pre-approval-validation.md` | read | L |
| All | `$SKILLS/sdd-common/references/state-scope.md` (scope + lifetime of persisted state) | read | L |

## Invocation Examples

| Request | Action |
|---------|--------|
| "sdd create steering" | Full steering workflow: product → tech → structure |
| "sdd resume steering" | Resume from last incomplete step |
| "sdd update steering [doc] with [change]" | Update mode — targeted edit + approval |

## Workflow

### Step 1: Pre-Flight Validation

Run pre-flight per `$SKILLS/sdd-common/references/pre-flight-protocol.md`.

```
.spec-workflow/sdd workspace/ensure-healthy.py --workspace .
```

**Document state detection** (MANDATORY — run before any doc creation):
```
.spec-workflow/sdd util/detect-doc-state.py \
  --category steering --target-doc <doc> --workspace .
```
Follow `recommended_action` from output:
- `collision_prompt` → present `steering-collision` prompt (see below)
- `recreate_prompt` → present `steering-recreate` prompt (see below)
- `create_fresh` → proceed to Step 2

```
.spec-workflow/sdd util/generate-prompt.py --type steering-collision
```

```
.spec-workflow/sdd util/generate-prompt.py --type steering-recreate
```

**User gathering** (from `user_gathering` field in output):
- If `required: true` → present inferred context summary from `context_available`, ask user to confirm or adjust before writing
- If `required: false` → proceed with codebase-derived content

| Check | Action on Failure |
|-------|-------------------|
| `.spec-workflow/` exists | Handled by pre-flight (see above) |
| No existing steering docs | Proceed to creation (Step 2+) |
| Steering docs exist + user wants full regeneration | Offer via structured prompt (see below) |
| Steering docs exist + user wants targeted edit | Route to Step 1.1 (update mode) |

**If steering docs exist and user wants full regeneration:**

Present the `steering-collision` prompt from the registry via AskQuestion:

```
.spec-workflow/sdd util/generate-prompt.py --type steering-collision
```

See `$SKILLS/sdd-common/references/prompt-conventions.md` § Integration Pattern.

### Step 1.1: Update Mode (Targeted Edit)

**Triggered when**: Steering docs exist AND user requests a specific change (not full regeneration).

**If the target doc(s) are not clear from the user's request**, clarify before reading any files:

Present the `steering-scope` prompt from the registry via AskQuestion:

```
.spec-workflow/sdd util/generate-prompt.py --type steering-scope
```

See `$SKILLS/sdd-common/references/prompt-conventions.md` § Integration Pattern.

**If the user has selected target doc(s) but NOT described the kind of change**,
present the `update-intent` prompt from the registry via AskQuestion
(pass `target_docs` as the selected doc names):

```
.spec-workflow/sdd util/generate-prompt.py --type update-intent --params target_docs=<value>
```

Route on the chosen intent per `references/steering-workflow.md` § Update Intent Routing.

Do NOT hand-roll a markdown option list in place of the registry prompt — see
`$SKILLS/sdd-common/references/prompt-conventions.md` § Integration Pattern.

**`user_gathering.required` in update mode.** Apply the routing table
in `$SKILLS/sdd-common/references/update-mode-user-gathering.md`
(§ Update-mode override). The reference owns the rule so creation-mode
and update-mode branches stay aligned in a single place.

Follow `$SKILLS/sdd-common/references/update-mode-workflow.md` with:

| Param | Value |
|-------|-------|
| doc-root | `.spec-workflow/steering/` |
| review skill | `sdd-review-steering-docs` |
| approval category | steering |
| target-name | steering |
| downstream rules | Cross-doc consistency note if multiple docs changed |
| thought-partner | `required-with-triage` |
| thought-partner-questions | See `references/steering-workflow.md` § Update Mode Exploration |
| thought-partner-depth | `full` |

### Step 2: Write product.md

**Purpose**: Define vision, goals, and user outcomes.

1. Resolve template: `.spec-workflow/sdd util/resolve-template.py --type product --content`
2. Use the `content` field from the JSON output (variables already substituted)
3. **Recreate detection** — before gathering user input, check for a prior version via `git show HEAD:.spec-workflow/steering/product.md`.
   - **If prior version exists (exit 0):** Present the `steering-recreate` prompt from the registry via AskQuestion (see command below).
     - **"Restore previous"** → write prior content to product.md, skip thought-partner, proceed to Step 3
     - **"Create fresh"** → continue with sub-step 4 (thought-partner engagement)
   - **If no prior version (exit non-0):** Continue with sub-step 4

```
.spec-workflow/sdd util/generate-prompt.py --type steering-recreate
```
4. Gather information from user about product vision and goals
5. Generate product vision and goals
6. Create `product.md` at `.spec-workflow/steering/product.md`

See `references/steering-workflow.md` § Phase 1 for detailed process.

### Step 3: Review and Approval for product.md

Run the Review and Approval Pipeline per `$SKILLS/sdd-common/references/review-approval-pipeline.md`. See § Pipeline Parameters (Step 3 row).

### Step 4: Write tech.md

**Purpose**: Document technology decisions and architecture.

1. Resolve template: `.spec-workflow/sdd util/resolve-template.py --type tech --content`
2. Use the `content` field from the JSON output (variables already substituted)
3. Analyze existing technology stack in the codebase
4. Document architectural decisions and patterns
5. Create `tech.md` at `.spec-workflow/steering/tech.md`

See `references/steering-workflow.md` § Phase 2 for detailed process.

### Step 5: Review and Approval for tech.md

Run the Review and Approval Pipeline per `$SKILLS/sdd-common/references/review-approval-pipeline.md`. See § Pipeline Parameters (Step 5 row).

### Step 6: Write structure.md

**Purpose**: Map codebase organization and patterns.

1. Resolve template: `.spec-workflow/sdd util/resolve-template.py --type structure --content`
2. Use the `content` field from the JSON output (variables already substituted)
3. Analyze directory structure and file organization
4. Document coding patterns and conventions
5. Create `structure.md` at `.spec-workflow/steering/structure.md`

See `references/steering-workflow.md` § Phase 3 for detailed process.

### Step 7: Review and Approval for structure.md

Run the Review and Approval Pipeline per `$SKILLS/sdd-common/references/review-approval-pipeline.md`. See § Pipeline Parameters (Step 7 row).

### Step 8: Final Review and Approval

Run the Review and Approval Pipeline per `$SKILLS/sdd-common/references/review-approval-pipeline.md`. See § Pipeline Parameters (Step 8 row).

On completion: Steering docs complete. Consider running `sdd create spec {name}` to create feature specs.

Steering docs will be automatically loaded by `sdd-create-spec` during Step 2 of spec creation to provide project context for requirements, design, and task authoring.

## Pipeline Parameters

All approval steps (3, 5, 7, 8) use the Review and Approval Pipeline with these parameters:

**Shared params:** `category: steering`, `target-name: steering`, `review_skill: sdd-review-steering-docs`, `max_fix_cycles: 2`

| Step | scope | doc | doc_list | title |
|------|-------|-----|----------|-------|
| 3 | `per-document` | product.md | `product.md` | Steering: product.md |
| 5 | `per-document` | tech.md | `tech.md` | Steering: tech.md |
| 7 | `per-document` | structure.md | `structure.md` | Steering: structure.md |
| 8 | `final` | (all) | `product.md, tech.md, structure.md` | Steering: Final Approval |

## Workflow Progress

**Step continuation applies.** See `$SKILLS/sdd-common/references/safety-rules.md` § Workflow Safety.

**Review gate pattern** (applies to all approval steps below):
See `$SKILLS/sdd-common/references/review-gate-pattern.md` for the full review gate workflow
(validate → review gate → approval, session modes, fix-loop TODO lifecycle).
**Fix-loop TODO lifecycle:** Pass `--parent-todo <step_id> --gate-id <step_id>`
to all `prepare-pipeline.py` phase calls. The launch output provides
`phase_commands` (exact next-step commands) and `todo_write_payload`
(pass directly to TodoWrite — do NOT reshape keys).

On any blocked/pending-calls response, follow `$SKILLS/sdd-common/references/review-approval-pipeline.md` § Pending Tool Calls Enforcement (covers `required_tool_calls` ordering and `next_action_sequence` recovery).

Example launch (Step 3): See `$SCRIPTS/sdd_core/command_templates.py::build_review_pipeline_launch_command` — the canonical builder. The launch shim is rendered onto the `handoffs[]` array of every steering envelope.

Copy this checklist and track progress:

```
- [ ] Step 1: Pre-flight validation — Triage: T0
  - → `steering-collision` prompt (if existing docs)
- [ ] Step 1.1: Update mode (if targeted edit) — Triage: T0/T1
  - → `steering-scope` prompt (if ambiguous)
  - → Validate (pre-approval-validation.md)
  - → `review-action` prompt (accept/review first/revise/discard)
  - → `approval-formal` prompt (Pattern B; `--no-skip` variant when the doc list terminates)
- [ ] Step 2: Write product.md
- [ ] Step 3: Review and Approval for product.md — review gate (review → fix → **re-review** → approve)
- [ ] Step 4: Write tech.md
- [ ] Step 5: Review and Approval for tech.md — review gate pattern
- [ ] Step 6: Write structure.md
- [ ] Step 7: Review and Approval for structure.md — review gate pattern
- [ ] Step 8: Final Review and Approval — review gate pattern
```

## Safety Rules

See `$SKILLS/sdd-common/references/safety-rules.md`. Key rules for this skill: Sequential steps (product → tech → structure); categoryName must be "steering"; Review and Approval Pipeline (`per-document`) for creation, Pipeline (`final`) for updates.

## Edge Cases

See `$SKILLS/sdd-common/references/common-edge-cases.md` for shared patterns (Template Missing, Approval Rejected, Resume Existing). Skill-specific edge cases:

| Situation | Action |
|-----------|--------|
| Any steering doc exists in `.spec-workflow/steering/` | Present `steering-collision` prompt from registry via AskQuestion. If only non-target docs exist, note as context and proceed. |
| Target doc deleted from tree but in git history | Present choice: (a) restore + enter review, (b) create from scratch, (c) cancel |
| User only wants one doc | Create requested doc, warn about missing context for later docs |
| Large codebase analysis timeout | Analyze in sections, document progressively |
| Targeted edit to non-existent doc | Fall back to creation mode for that doc |
| User changes scope from targeted to full regeneration | Switch to existing creation flow (Step 2+) |
| Update spans multiple docs | Batch if same logical change, sequential if independent changes |
| Single doc completes the set (all 3 exist and approved) | Recommend final review: "All steering docs are now approved. Consider running `sdd review steering` for cross-document consistency validation." |

Invocation for the `steering-collision` prompt referenced above:

```
.spec-workflow/sdd util/generate-prompt.py --type steering-collision
```

## Completion

Steering doc creation complete. To create a spec, run `sdd create spec {name}`.

## Reference Files

- Steering workflow: references/steering-workflow.md
- Approval flow: $SKILLS/sdd-common/references/approval-flow.md
- Template compliance: $SKILLS/sdd-common/references/template-compliance.md
