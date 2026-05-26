---
name: sdd-create-prd
description: Creates PRD documents through a conversational thought-partner workflow with
  readiness gates, stress testing, and approval. Guides the PM through problem
  exploration, goal setting, scope decisions, requirements drafting, and stress testing
  before generating the final document. Use when asked to create a PRD, write a PRD,
  resume a PRD, update a PRD, or start a product requirements document.
allowed-tools: Read Write Edit Bash Agent AskQuestion AskUserQuestion TaskCreate TaskUpdate WebFetch
metadata:
  version: 3.3.1
  category: development
  dependencies: [sdd-common, sdd-review-prd, sdd-manage-status]
  author: membership-platforms-sdd-guild
---

> **Paths:** See `$SKILLS/sdd-common/references/path-conventions.md`. Scripts: `.spec-workflow/sdd {group}/{script}.py`.

# SDD: Create PRD

Creates PRD documents through a 6-step conversational workflow
(plus pre-flight, review, and post-draft steps).
Two modes supported:

| Mode | Trigger | Behavior |
|------|---------|----------|
| **Guided** (default) | Default | Agent drives the session — asks questions, assesses readiness, advances steps |
| **Self-directed** | User signals they want to drive | Agent responds to prompts but doesn't proactively advance |

## Contents

- [Dependencies](#dependencies)
- [Invocation Examples](#invocation-examples)
- [Session Modes](#session-modes)
- [Thought-Partner Contract](#thought-partner-contract)
- [Naming Convention](#naming-convention)
- [Pipeline Parameters](#pipeline-parameters)
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
| Step 0 | `$SKILLS/sdd-common/references/tool-patterns.md` | read | L |
| Step 0 | `$SKILLS/sdd-common/references/pre-flight-protocol.md` | read | L |
| Step 0 | `$SKILLS/sdd-common/scripts/spec/check-status.py` | run | L |
| Step 0 (discovery) | `$SKILLS/sdd-common/scripts/discovery/validate-manifest.py` | run | L |
| Step 0.3 | `$SKILLS/sdd-common/references/update-mode-workflow.md` | read | L |
| Steps 1–5 | `$SKILLS/sdd-create-prd/references/prd-workflow.md` | read | L |
| Steps 1–5 | `$SKILLS/sdd-common/scripts/prd/write-session-state.py` | run | L |
| Steps 1, 3 | `$SKILLS/sdd-create-prd/references/readiness-checks.md` | read | M |
| Step 5 | `$SKILLS/sdd-create-prd/references/stress-test-protocol.md` | read | M |
| Step 6 (validate) | `$SKILLS/sdd-common/scripts/prd/validate-readiness.py` | run | L |
| Step 6 (template) | `$SKILLS/sdd-common/references/template-compliance.md` | read | M |
| Step 6.1 (validate) | `$SKILLS/sdd-common/scripts/prd/validate-prd.py` | run | L |
| Step 7 | `$SKILLS/sdd-common/references/review-approval-pipeline.md` | read | L |
| Step 7 | `$SKILLS/sdd-common/references/approval-flow.md` § Category Conventions (category: "discovery") | read | L |
| Step 8 (discovery) | `$SKILLS/sdd-common/scripts/discovery/update-manifest.py` | run | L |
| Edge cases | `$SKILLS/sdd-create-prd/references/prd-edge-cases.md` | read | M |
| All | `$SKILLS/sdd-common/references/state-scope.md` (scope + lifetime of persisted state) | read | L |

## Invocation Examples

| Request | Action | Mode |
|---------|--------|------|
| "sdd create prd [feature-name]" | Create PRD as `prd.md` (default name) | Guided |
| "sdd create prd [feature-name] --name prd-payments.md" | Create PRD with custom name | Guided |
| "sdd prd [feature-name]" | Full PRD workflow | Guided |
| "sdd resume prd [feature-name]" | Resume from last step (uses name from session state) | Auto-detect |
| "sdd update prd [feature-name] [prd-name]" | Update mode for a specific PRD | Self-directed |

## Session Modes

| Mode | Detection | Behavior |
|------|-----------|----------|
| Guided | Default, or user says "guide me" | Agent asks questions, assesses readiness, controls step flow |
| Self-directed | User provides pre-written problem/goals, or says "I'll drive" | Agent assists but follows user's lead |

## Thought-Partner Contract

This skill operates as a **thought partner for PMs** — not an autonomous document generator.

| Principle | Rule |
|-----------|------|
| **Ask, don't assume** | When information is missing, ask the PM. Never fill gaps with plausible-sounding content. |
| **Challenge, don't accept** | Push back on weak answers. "That sounds reasonable" is not useful. "What would a skeptic say about that?" is. |
| **Record, don't resolve** | When the PM says "I don't know", record it as an open question with a Blocks entry. Do not attempt to answer it. |
| **Source everything** | Every statement in the generated PRD must trace to: (a) something the PM said in conversation, (b) the steering doc, or (c) an explicit open question. No other sources. |
| **Flag AI-generated content** | If the agent generates example text to illustrate a point during conversation, prefix it with "For example:" and ask the PM to confirm or rewrite before it enters the document. |

## Naming Convention

- Feature name: kebab-case (e.g., `loyalty-redemption`, `payment-flow`)
- PRD filename: must contain `prd` (case-insensitive). Default: `prd.md`. See `$SKILLS/sdd-common/references/general-principles.md` § PRD Filename Convention.
- Path: `.spec-workflow/discovery/{feature-name}/{prd-name}`
- A discovery project may hold multiple PRDs. Each gets its own artifact entry in `manifest.json`.
- Filename uniqueness is enforced by the manifest (no duplicate `file` values).

## Pipeline Parameters

All approval steps use the Review and Approval Pipeline (`$SKILLS/sdd-common/references/review-approval-pipeline.md`) with these parameters:

**Shared params:** `category: discovery`, `target-name: {feature-name}`, `review_skill: sdd-review-prd`, `max_fix_cycles: 2`

| Step | scope | doc | doc_list | title |
|------|-------|-----|----------|-------|
| 7 | `per-document` | {prd-name} | `{prd-name}` | PRD: {feature-name}/{prd-name} |

> **Note:** Since PRD produces a single document, there is no separate `final` scope step. The `per-document` pipeline at Step 7 serves as both the per-document and final gate.

## Workflow

### Step 0: Pre-Flight Validation

Run pre-flight per `$SKILLS/sdd-common/references/pre-flight-protocol.md`, then discovery validation (auto-scaffold if missing).

**Document state detection** (MANDATORY — run before any doc creation). Category is `discovery`.
```
.spec-workflow/sdd util/detect-doc-state.py --category discovery --target-name "{feature-name}" \
  --target-doc {prd-name} --workspace .
```
Follow `recommended_action` from output:
- `collision_prompt` → present collision prompt
- `recreate_prompt` → present recreate choice
- `create_fresh` → proceed to Step 0.1

**User gathering** (from `user_gathering` field in output):
- If `required: true` → present inferred context summary from `context_available`, ask user to confirm or adjust before writing
- If `required: false` → proceed with codebase-derived content

Determine the situation:

**PRD `{prd-name}` doesn't exist?** → Step 0.1
**PRD exists + user wants regeneration?** → Prompt: resume / new name / overwrite → Step 0.1
**PRD exists + user wants targeted edit?** → Step 0.3 (update mode)

If project has other PRDs, list them and offer: (a) proceed, (b) switch to update, (c) cancel.

See `references/prd-workflow.md` § Step 0 for script commands and detailed routing.

### Step 0.1: Load Context

Read steering docs + any prior PRDs relevant to this feature.
Reflect back 2-3 most relevant context points. If steering docs
are missing, warn and offer to create them first via
sdd-create-steering handoff.

```
# Read if they exist
.spec-workflow/steering/product.md
.spec-workflow/steering/tech.md
.spec-workflow/steering/structure.md
```

### Step 0.2: Establish Session Mode

Detect guided vs self-directed. In guided mode, tell the user:
"I'll drive — I'll ask questions at each step and tell you when
we're ready to advance."

### Step 0.3: Update Mode (Targeted Edit)

**Triggered when**: PRD exists AND user requests a specific change (not full regeneration).

Follow `$SKILLS/sdd-common/references/update-mode-workflow.md` with:

| Param | Value |
|-------|-------|
| doc-root | `.spec-workflow/discovery/{feature-name}/` |
| review skill | `sdd-review-prd` |
| approval category | discovery |
| target-name | {feature-name} |
| downstream rules | See table below |
| thought-partner | `required-with-triage` |
| thought-partner-questions | See `references/prd-workflow.md` § Update Mode Exploration |
| thought-partner-depth | `full` |

**Downstream impact rules:**

| Document Changed | Downstream Warning |
|------------------|--------------------|
| {prd-name} | "Requirements, design, and tasks may need updates to reflect PRD changes. Run `sdd review spec {name}` after approval." |

### Step 1: Problem Exploration

See `references/prd-workflow.md` § Step 1.

If the problem statement drifts into solution vocabulary, the pre-requirements gate surfaces a `problem_statement_solution_marker` advisory — rewrite the statement to describe the user-visible problem, then re-run `.spec-workflow/sdd prd/write-session-state.py` to resync the session so `sdd update prd` re-reads the corrected framing.

### Step 2: Goals and Success Criteria

See `references/prd-workflow.md` § Step 2.

### Step 3: Scope Decision

See `references/prd-workflow.md` § Step 3.

### Readiness Check 1: Before Requirements

After each conversational step (1, 2, 3), first get the expected schema, then write progressive session state:
```
.spec-workflow/sdd prd/write-session-state.py --target "{feature-name}" --step N --show-schema
```
```
.spec-workflow/sdd prd/write-session-state.py --target "{feature-name}" --step N --data '{...}'
```

If the write fails, re-read the error context, adjust the JSON payload to match the schema, and retry (max 2 attempts).

Then run `.spec-workflow/sdd prd/validate-readiness.py` with `--session-file` to check structural completeness
of Steps 1-3 output, then apply readiness-checks.md § Pre-Requirements Gate for judgment-based criteria.

```
.spec-workflow/sdd prd/validate-readiness.py --target "{feature-name}" --gate pre-requirements --session-file
```

If script returns exit 1 (structural gaps) → surface missing items, resolve before proceeding.
If script returns exit 0 → proceed to judgment check per readiness-checks.md.

### Step 4: Requirements Drafting

**Session state shape**: See [session-state-schema.md](references/session-state-schema.md)

See `references/prd-workflow.md` § Step 4.

### Step 5: Stress Testing

See `references/stress-test-protocol.md` and `references/prd-workflow.md` § Step 5.

### Readiness Check 2: Before Generation

Write session state for Steps 4 and 5 using the schema-then-write pattern from Readiness Check 1 above.

Then run `.spec-workflow/sdd prd/validate-readiness.py --gate pre-generation --session-file` to verify structural
requirements are met, then apply readiness-checks.md § Pre-Generation Gate.

```
.spec-workflow/sdd prd/validate-readiness.py --target "{feature-name}" --gate pre-generation --session-file
```

### Step 6: Document Generation

See `references/prd-workflow.md` § Step 6.

After generating the PRD document, clean up the session state file:
```
.spec-workflow/sdd prd/write-session-state.py --target "{feature-name}" --delete
```

### Step 6.1: Post-Generation Validation

Run deterministic validation on the generated document:

```
.spec-workflow/sdd prd/validate-prd.py ".spec-workflow/discovery/{feature-name}/{prd-name}"
```

The script checks:
- WHEN/THEN format in requirements (exit 0 = pass, exit 1 = issues found)
- All 6 NFR categories present and non-placeholder
- Open questions have Owner + Due Date + Blocks columns populated
- Alternatives Considered section non-empty
- Rollout plan has Success Gate + Rollback Plan columns

If validation fails → fix issues in {prd-name} → re-run validation (feedback loop, max 2 cycles).

### Step 6.2: Register PRD in Discovery Manifest

Register the PRD artifact in the manifest immediately after validation passes,
so the review sub-agent at Step 7 can discover it:

```
.spec-workflow/sdd discovery/update-manifest.py --name "{feature-name}" add-artifact --file "{prd-name}"
```

### Step 7: Review and Approval for {prd-name}

> **Before first approval:** Read `$SKILLS/sdd-common/references/approval-flow.md` § Pattern B for the
> approval lifecycle (request → update → delete) and § Category Conventions
> for the storage path (`approvals/{categoryName}/`).

Run the Review and Approval Pipeline per `$SKILLS/sdd-common/references/review-approval-pipeline.md`. See § Pipeline Parameters (Step 7 row).

### Step 8: Post-Draft Maintenance

See `references/prd-workflow.md` § Post-Draft.

1. Suggest steering doc updates based on session decisions
2. Note open questions that need resolution
3. **Discovery integration:** Update artifact status (registration was done in Step 6.2):
   ```
   .spec-workflow/sdd discovery/update-manifest.py --name "{feature-name}" set-artifact-status --file "{prd-name}" --status "approved"
   ```
4. **Update Document Metadata** (post-approval): Update the PRD's Document Metadata table — change `Status` from `Draft` to `Approved` and bump `Version` (e.g., `0.1` → `1.0`). This is a text edit to the PRD file — no script needed.
5. Recommend next step: `sdd create spec {feature-name}` to begin spec creation with PRD as input context

### Step 9: Open Question Resolution (ongoing)

When an open question in the PRD is resolved:

1. Update the PRD: remove from Open Questions table, update affected requirements/NFRs
2. Re-run `.spec-workflow/sdd prd/validate-prd.py` to verify structural integrity
3. Bump the version number in Document Metadata
4. Update artifact status:
   ```
   .spec-workflow/sdd discovery/update-manifest.py --name "{feature-name}" set-artifact-status --file "{prd-name}" --status "in-review"
   ```

## Workflow Progress

**Step continuation applies.** See `$SKILLS/sdd-common/references/safety-rules.md` § Workflow Safety.

**Review gate pattern** (applies to approval step below):
See `$SKILLS/sdd-common/references/review-gate-pattern.md` for the full review gate workflow
(validate → review gate → approval, session modes, fix-loop TODO lifecycle).

Example launch (Step 7):
```
.spec-workflow/sdd review/pipeline-tick.py --category discovery --target-name "{feature-name}" \
  --phase launch --review-skill sdd-review-prd \
  --workspace . --doc-list "{prd-name}" \
  --scope per-document \
  --workflow-mode create \
  --parent-todo step7 --gate-id step7
```

On any blocked/pending-calls response, follow `$SKILLS/sdd-common/references/review-approval-pipeline.md` § Pending Tool Calls Enforcement (covers `required_tool_calls` ordering and `next_action_sequence` recovery).

**Progress checklist**: See `references/progress-checklist.md` — copy the fenced checklist into notes to track progress.

## Safety Rules

See `$SKILLS/sdd-common/references/safety-rules.md`. Key rules for this skill: Sequential steps (problem → goals → scope → requirements → stress test → generate); one PRD creation session at a time; do not advance past a readiness gate until criteria are met; Review and Approval Pipeline (`per-document`) for approval.

Do not invent content the user didn't provide. When structural validation fails (readiness gates, post-generation checks), surface the gap to the PM and ask them to provide the missing information — do not fill it in. The PM is the author; the agent is the thought partner.

## Edge Cases

See `references/prd-edge-cases.md` for skill-specific edge cases and
`$SKILLS/sdd-common/references/common-edge-cases.md` for shared patterns.

## Completion

PRD creation complete. To create a spec, run `sdd create spec {feature-name}`.

## Reference Files

- PRD workflow: references/prd-workflow.md
- Readiness checks: references/readiness-checks.md
- Stress test protocol: references/stress-test-protocol.md
- Progress checklist: references/progress-checklist.md
- Edge cases: references/prd-edge-cases.md
- Approval flow: $SKILLS/sdd-common/references/approval-flow.md
- Template compliance: $SKILLS/sdd-common/references/template-compliance.md

## Handoffs

See `references/handoffs.md` (generated from `$SCRIPTS/handoff-registry.json`).
Regenerate via `.spec-workflow/sdd internal_lints/skill_md_handoff_table.py --rewrite`.
