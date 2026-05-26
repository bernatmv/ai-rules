---
name: sdd-review-steering-docs
description: Reviews SDD steering document quality (product.md, tech.md, structure.md)
  for completeness, cross-document consistency, and project drift. Use when asked to
  review steering docs or detect drift.
allowed-tools: Read Write Edit Bash Agent AskQuestion AskUserQuestion TaskCreate TaskUpdate WebFetch
metadata:
  version: 3.3.1
  category: review
  dependencies: [sdd-common]
  author: membership-platforms-sdd-guild
---

> **Paths:** See `$SKILLS/sdd-common/references/path-conventions.md`. Scripts: `.spec-workflow/sdd {group}/{script}.py`.

# SDD: Review Steering Documents

Reviews steering documents against quality checklists. Supports reviewing all/specific docs, pending approvals, and detecting project state drift.

Severity, scoring, and report conventions: see `$SKILLS/sdd-common/references/review-conventions.md`.

## Contents

- [Dependencies](#dependencies)
- [Invocation Examples](#invocation-examples)
- [Workflow](#workflow)
- [Workflow Progress](#workflow-progress)
- [Project State Drift Detection](#project-state-drift-detection)
- [Human approval ceremony](#human-approval-ceremony)
- [Completion](#completion)
- [Reference Files](#reference-files)

## Dependencies

> **Load on demand**: Read each file only when the workflow reaches that step — not all upfront.

| Step | File | Kind | Freedom |
|------|------|------|:-:|
| Step 1 | `$SKILLS/sdd-common/references/tool-patterns.md` (invocation contract for every shim call in this workflow) | read | L |
| Step 1 | `$SKILLS/sdd-common/references/parallel-batch-hygiene.md` (batch composition for Step-1 discovery call) | read | L |
| Step 1 | `$SKILLS/sdd-common/scripts/spec/check-status.py` (`--type steering` discovery) | run | L |
| Steps 1–4 | `$SKILLS/sdd-common/references/review-workflow-base.md` (shared workflow skeleton) | read | L |
| Step 3 | `$SKILLS/sdd-common/references/approval-flow.md` (resilient discovery) | read | L |
| Step 5.1 | `$SKILLS/sdd-common/references/template-compliance.md` | read | M |
| Step 5.2 | `$SKILLS/sdd-common/references/size-limits.md` | read | M |
| Step 5.3 | `$SKILLS/sdd-common/references/cross-validation.md` | read | M |
| Step 5.4 | `$SKILLS/sdd-common/references/general-principles.md` (design-level lens) | read | M |
| Step 7 | `$SKILLS/sdd-common/references/review-conventions.md` (report skeleton) | read | L |
| Step 7.1 | `$SKILLS/sdd-common/scripts/review/update-quality.py` (artifact writer) | run | L |
| Step 7.1 | `$SKILLS/sdd-review-steering-docs/references/artifact-assessment-format.md` | read | M |
| All | `$SKILLS/sdd-common/references/state-scope.md` (scope + lifetime of persisted state) | read | L |

## Invocation Examples

| Request | Action |
|---------|--------|
| "sdd review steering" | Review all steering docs |
| "sdd review steering [doc]" | Review specific doc |
| "sdd detect drift" | Detect project state drift |

## Workflow

### Parameters

| Parameter | Value |
|-----------|-------|
| DISCOVERY_TOOL | `spec/check-status.py --type steering` |
| DOCUMENT_LIST | `product.md` — Product vision and goals · `tech.md` — Technology stack and architecture · `structure.md` — Codebase organization |
| LOCATE_STRATEGY | Search in priority order: 1. `.spec-workflow/steering/` (primary) 2. Project root 3. `docs/` folder |
| STATUS_SPEC_NAME | `"steering"` |
| STATUS_EXTRAS | Follow the **Resilient Steering Approval Discovery** procedure in `$SKILLS/sdd-common/references/approval-flow.md`. |
| CRITERIA_MAPPING | product.md → `references/validation-criteria-product.md` · tech.md → `references/validation-criteria-tech.md` · structure.md → `references/validation-criteria-structure.md` |
| CROSS_VALIDATION_PAIRS | product↔tech, product↔structure, tech↔structure |

### Steps 1–4: Document Discovery through Scope

**1. Discover** — Run `.spec-workflow/sdd spec/check-status.py --type steering` to enumerate docs
**2. Locate** — Search in `.spec-workflow/steering/`, project root, `docs/`
**3. Status** — Check pending approvals per `$SKILLS/sdd-common/references/approval-flow.md`
**4. Scope** — Determine review scope (all docs or specific doc)

For detailed procedures, see `$SKILLS/sdd-common/references/review-workflow-base.md` Base Steps A–D.

### Step 5: Apply Checklists

Follow **Base Step E** from `$SKILLS/sdd-common/references/review-workflow-base.md`.

### Step 5.1: Template Compliance Check

Follow **Base Step F** from `$SKILLS/sdd-common/references/review-workflow-base.md`.

### Step 5.2: Document Size Check

For each document, apply the **Document Size Limits** check from `$SKILLS/sdd-common/references/size-limits.md`.
Use the simplification recommendation template from that file when a document exceeds its limit.
Include per-document results in the report (Step 7).

### Step 5.3: Cross-Document Validation

Follow **Base Step G** from `$SKILLS/sdd-common/references/review-workflow-base.md`
with these pairs: product↔tech, product↔structure, tech↔structure. The pair-by-pair "must check" matrix lives in `$SKILLS/sdd-common/references/cross-validation.md`.

**Findings Summaries:** For each conflict, gap, duplication, or drift found, produce a one-sentence `summary` (max ~200 chars) explaining what the issue is. Include these as `findings` in the assessment JSON (Step 7.1).

### Step 5.4: Design-Level Principles Check

Evaluate steering docs against design-level checks from `$SKILLS/sdd-common/references/general-principles.md`.
Use the override mechanism if user supplies custom principles. Generate a principle
scorecard table and include in the report (Step 7).

### Step 6: AI Comprehension Test

| Document | Question |
|----------|----------|
| product.md | What does this project do? |
| tech.md | How is it built? |
| structure.md | Where does key functionality live? |

**Full test** (all docs reviewed): Propose implementing a simple feature using all three docs.

If you cannot answer confidently, the documents need improvement.

### Step 7: Generate Report

Follow **Base Step H** from `$SKILLS/sdd-common/references/review-workflow-base.md`, adding these skill-specific sections:

1. **Per-Document**: score (X/5), line count, checklist results, issues, recommendations; if over limit per `$SKILLS/sdd-common/references/size-limits.md`, include simplification table
2. **Cross-Validation Summary**: duplication/conflict/gap counts with findings table (from Step 5.3)
3. **Design-Level Principles Scorecard**: principle ratings from Step 5.4
4. **AI Comprehension Test**: answer 3 questions + confidence level (HIGH/MEDIUM/LOW)

### Step 7.1: Write Quality Artifact

Read `references/artifact-assessment-format.md` for the exact JSON format, exclusion list, and run command.

## Workflow Progress

Copy this checklist and track progress:

```
- [ ] Steps 1–4: Discover docs, locate files, check approval status, determine scope — Triage: T0
- [ ] Step 5 (product.md): Apply validation-criteria-product.md
- [ ] Step 5 (tech.md): Apply validation-criteria-tech.md
- [ ] Step 5 (structure.md): Apply validation-criteria-structure.md
- [ ] Step 5.1: Template compliance check (via sdd-common)
- [ ] Step 5.2: Document size check (200-line limit)
- [ ] Step 5.3: Cross-document consistency checks
- [ ] Step 5.4: Design-level principles check
- [ ] Step 6: AI comprehension test
- [ ] Step 7: Generate review report with per-document scores
- [ ] Step 7.1: Write quality artifact (`.spec-workflow/sdd review/update-quality.py`)
```

## Project State Drift Detection

For drift detection workflow, read `references/drift-detection.md` and follow its steps.

### Drift Detection Progress

Copy this checklist and track progress:

```
- [ ] Step D1: Identify drift sources (codebase, dependencies, config)
- [ ] Step D2: Compare steering docs against actual project state
- [ ] Step D3: Flag discrepancies (outdated tech, missing structure entries)
- [ ] Step D4: Generate drift report with recommended updates
```

## Human approval ceremony

Follow [`human-approval-ceremony.md`]($SKILLS/sdd-common/references/human-approval-ceremony.md) with `target_label="{doc-label}"` before any `.spec-workflow/sdd approval/update-status.py … approve`.

## Completion

Follow **Base Step I** from `$SKILLS/sdd-common/references/review-workflow-base.md`.

Steering review complete. To approve, run `sdd approve steering`. To request revision, ask for changes.

## Reference Files

- Base workflow steps: $SKILLS/sdd-common/references/review-workflow-base.md
- Review conventions: $SKILLS/sdd-common/references/review-conventions.md
- Template compliance: $SKILLS/sdd-common/references/template-compliance.md
- Cross-validation (common): $SKILLS/sdd-common/references/cross-validation.md
- General principles (DRY, SOLID, KISS): $SKILLS/sdd-common/references/general-principles.md
- Size limits: $SKILLS/sdd-common/references/size-limits.md
- Validation criteria index (routes to the three files below): references/validation-criteria.md
- Validation criteria (product): references/validation-criteria-product.md
- Validation criteria (tech): references/validation-criteria-tech.md
- Validation criteria (structure): references/validation-criteria-structure.md
- Drift detection: references/drift-detection.md
- Cross-validation (steering): references/cross-validation-criteria.md
- Quality artifact format (Step 7.1): references/artifact-assessment-format.md
