---
name: sdd-review-spec-docs
description: Reviews SDD spec document quality (requirements.md, ui-design.md, design.md,
  tasks.md) for completeness, testing coverage, template compliance, and cross-document
  consistency. Use when asked to review, validate, or check spec documents, requirements,
  design, tasks, testing coverage, traceability, or implementation readiness.
allowed-tools: Read Write Edit Bash Agent AskQuestion AskUserQuestion TaskCreate TaskUpdate WebFetch
metadata:
  version: 3.3.1
  category: review
  dependencies: [sdd-common]
  author: membership-platforms-sdd-guild
---

> **Paths:** See `$SKILLS/sdd-common/references/path-conventions.md`. Scripts: `.spec-workflow/sdd {group}/{script}.py`.

# SDD: Review Spec Documents

Reviews spec documents against quality checklists. Validates requirements.md, ui-design.md (when present), design.md, and tasks.md with emphasis on testing coverage and cross-document consistency.

Severity, scoring, and report conventions: see `$SKILLS/sdd-common/references/review-conventions.md`.

## Contents

- [Dependencies](#dependencies)
- [Invocation Examples](#invocation-examples)
- [Pre-Review: Steering Doc Check](#pre-review-steering-doc-check)
- [Workflow](#workflow)
- [Workflow Progress](#workflow-progress)
- [Workspace Mode](#workspace-mode)
- [Safety Rules](#safety-rules)
- [Edge Cases](#edge-cases)
- [Human approval ceremony](#human-approval-ceremony)
- [Completion](#completion)
- [Reference Files](#reference-files)

## Dependencies

> **Load on demand**: Read each file only when the workflow reaches that step — not all upfront.

| Step | File | Kind | Freedom |
|------|------|------|:-:|
| Step 1 | `$SKILLS/sdd-common/references/tool-patterns.md` (invocation contract for every shim call in this workflow) | read | L |
| Step 1 | `$SKILLS/sdd-common/references/parallel-batch-hygiene.md` (batch composition for Step-1 discovery call) | read | L |
| Step 1 | `$SKILLS/sdd-common/scripts/spec/check-status.py` (`--spec-name` discovery) | run | L |
| Steps 1–4 | `$SKILLS/sdd-common/references/review-workflow-base.md` (shared workflow skeleton) | read | L |
| Step 5.1 | `$SKILLS/sdd-common/references/template-compliance.md` | read | M |
| Step 5.2 | `$SKILLS/sdd-review-spec-docs/references/validation-criteria-design.md` | read | M |
| Step 5.2 | `$SKILLS/sdd-review-spec-docs/references/validation-criteria-tasks.md` (testing coverage) | read | M |
| Step 5.2 | `$SKILLS/sdd-review-spec-docs/references/testing-coverage.md` | read | M |
| Step 5.3 | `$SKILLS/sdd-common/references/cross-validation.md` | read | M |
| Step 5.4 | `$SKILLS/sdd-common/references/task-validation-rules.md` (deterministic checks) | read | M |
| Step 9 | `$SKILLS/sdd-common/references/review-conventions.md` (report skeleton) | read | L |
| Step 9.1 | `$SKILLS/sdd-review-spec-docs/references/artifact-assessment-format.md` | read | M |
| Step 8 | `$SKILLS/sdd-review-spec-docs/references/bug-fix-criteria.md` (additional bug fix criteria) | read | M |
| Conditional | `$SKILLS/sdd-common/references/detection-rules.md` (bug fix spec detection) | read | M |
| Step 8 | `$SKILLS/sdd-common/references/approval-flow.md` (§ Bundled vs per-document approval shape) | read | L |
| All | `$SKILLS/sdd-common/references/state-scope.md` (scope + lifetime of persisted state) | read | L |

## Invocation Examples

| Request | Action |
|---------|--------|
| "sdd review spec [name]" | Review all docs in spec |
| "sdd review spec [name] [doc]" | Review specific doc |
| "sdd review all specs" | Review all available specs |

## Pre-Review: Steering Doc Check

Before reviewing specs, verify steering docs are current. If tech.md or structure.md have drifted from the codebase, flag a `⚠️ Steering Doc Warning` in the report with the drift type, impact, and a recommendation to run `sdd detect drift` first.

## Workflow

### Parameters

| Parameter | Value |
|-----------|-------|
| DISCOVERY_TOOL | `spec/check-status.py` |
| DOCUMENT_LIST | `requirements.md` — Functional and non-functional requirements · `ui-design.md` (optional) — UI/UX layout, components, interactions, accessibility · `design.md` — Technical design and testing strategy · `tasks.md` — Implementation breakdown with traceability |
| LOCATE_STRATEGY | Specs live in `.spec-workflow/specs/[spec-name]/`. Match by exact name, partial substring, or fuzzy closest match. |
| STATUS_SPEC_NAME | `"[spec-name]"` |
| STATUS_EXTRAS | (none) |
| CRITERIA_MAPPING | requirements.md → `references/validation-criteria-requirements.md` · ui-design.md → `references/validation-criteria-ui-design.md` (when present) · design.md → `references/validation-criteria-design.md` · tasks.md → `references/validation-criteria-tasks.md` |
| CROSS_VALIDATION_PAIRS | req↔design, design↔tasks, req↔tasks; when ui-design.md present: req↔ui-design, ui-design↔design |

### Steps 1–5.1: Discovery, Scope, Checklists, Template Compliance

**1. Discover** — Run `.spec-workflow/sdd spec/check-status.py --target {spec-name}` to enumerate docs
**2. Locate** — Search in `.spec-workflow/specs/{spec-name}/`
**3. Status** — Check pending approvals per `$SKILLS/sdd-common/references/approval-flow.md`
**4. Scope** — Determine review scope (all docs or specific doc)
**5. Checklists** — Load per-doc validation criteria from CRITERIA_MAPPING
**5.1. Template Compliance** — Run compliance check per `$SKILLS/sdd-common/references/template-compliance.md`

For detailed procedures, see `$SKILLS/sdd-common/references/review-workflow-base.md` Base Steps A–F.

### Step 5.2: Testing Coverage Assessment

See `references/testing-coverage.md` § Criteria Table for the full assessment criteria and thoroughness rating scale.

### Step 5.3: Cross-Document Validation

Follow **Base Step G** from `$SKILLS/sdd-common/references/review-workflow-base.md`
with these pairs: req↔design, design↔tasks, req↔tasks.

**Findings Summaries:** For each conflict, gap, or duplication found, produce a one-sentence `summary` (max ~200 chars) explaining what the issue is. Include these as `findings` in the assessment JSON (Step 9.1).

### Step 5.4: Tier 1 Deterministic Checks

See `references/testing-coverage.md` § Tier 1 Deterministic Checks for script invocations, authoritative facet IDs, and score interpretation rules.

### Step 6: Refactoring Validation (when applicable)

Apply the checklists from `$SKILLS/sdd-common/references/refactoring-validation.md` using the
**Spec Review** lens. Choose Objectives-Based or Function Parity per the
approach selection rules in that file.

### Step 7: Implementation Readiness Test

| Document | Question |
|----------|----------|
| requirements.md | Can each requirement be independently verified? |
| design.md | Are all components implementable without clarification? |
| tasks.md | Can a developer start each task immediately? |

**Full test** (all docs reviewed): Walk through implementing a requirement using design architecture and task breakdown.

### Step 8: Bug Fix Spec Handling

If spec is a bug fix (see **Bug Fix Spec Detection** in `$SKILLS/sdd-common/references/detection-rules.md`), also read and apply `references/bug-fix-criteria.md` for additional requirements.md and design.md criteria.

### Step 9: Generate Report

Follow **Base Step H** from `$SKILLS/sdd-common/references/review-workflow-base.md`, adding these skill-specific sections:

1. **Per-Document**: score (X/max), checklist results, issues found; for design.md include testing strategy assessment; for tasks.md include requirements traceability table
2. **Cross-Validation Summary**: duplication/conflict/gap counts with findings table (from Step 5.3)
3. **Refactoring Validation** (when applicable): type, approach, results per `$SKILLS/sdd-common/references/refactoring-validation.md`
4. **Implementation Readiness**: confidence level + sample walkthrough
5. **Testing Thoroughness**: Comprehensive / Adequate / Basic / Insufficient

### Step 9.1: Write Quality Artifact

Run:

```
.spec-workflow/sdd review/update-quality.py --target {spec-name} \
  --tier2-payload <inline-json>
```

The Tier-2 payload schema, exclusion list, and inline-JSON examples
live in `references/artifact-assessment-format.md`. Tier 1 facets are
script-determined — do not include them in `--tier2-payload`.

## Workflow Progress

Copy this checklist and track progress:

```
- [ ] Pre-check: Verify steering docs are current (flag warning if drifted)
- [ ] Step 1: Discover spec folder and identify documents to review — Triage: T0
- [ ] Step 2: Detect spec type (standard vs bug-fix)
- [ ] Step 3: Check pending approvals (if reviewing for approval)
- [ ] Step 4: Load validation criteria for each document type
- [ ] Step 5 (requirements.md): Apply validation-criteria-requirements.md
- [ ] Step 5 (design.md): Apply validation-criteria-design.md
- [ ] Step 5 (tasks.md): Apply validation-criteria-tasks.md
- [ ] Step 5.1: Template compliance check (via sdd-common)
- [ ] Step 5.2: Assess testing coverage
- [ ] Step 5.3: Run cross-document consistency checks
- [ ] Step 5.4: Run Tier 1 deterministic checks (lint-tasks.py, check-traceability.py)
- [ ] Step 6: Refactoring validation (if applicable)
- [ ] Step 7: Run implementation readiness test
- [ ] Step 8: Bug fix spec handling (if applicable)
- [ ] Step 9: Generate consolidated review report with scores
- [ ] Step 9.1: Run `.spec-workflow/sdd review/update-quality.py` to write quality artifact
```

## Workspace Mode

When invoked with a `Workspace phase` parameter, apply these step overrides:

| Step | Phase R | Phase D | Phase T |
|------|---------|---------|---------|
| 5.2 (testing coverage) | Available docs only | Available docs only | All docs |
| 5.3 (cross-validation) | Skip (< 2 docs) | Execute (req + design) | Execute (all pairs) |
| 5.4 (tier 1 checks) | Skip (no tasks.md) | Skip (no tasks.md) | Execute |
| 6 (refactoring) | Skip | Skip unless applicable | Execute if applicable |
| 7 (implementation readiness) | Skip | Execute | Execute |

All other steps execute normally regardless of phase.

## Safety Rules

See `$SKILLS/sdd-common/references/review-safety-rules.md` for shared rules.

## Edge Cases

- If a document section is empty, score it as INCOMPLETE rather than FAIL
- If template compliance check fails, still complete the full review
- If cross-document validation finds missing docs, review available docs only

## Human approval ceremony

Follow [`human-approval-ceremony.md`]($SKILLS/sdd-common/references/human-approval-ceremony.md) with `target_label="{spec-name}"` before any `.spec-workflow/sdd approval/update-status.py … approve`.

## Completion

Follow **Base Step I** from `$SKILLS/sdd-common/references/review-workflow-base.md`.

Spec review complete. To approve, run `sdd approve spec {spec-name}`. To request revision, run `sdd request revision {spec-name}`.

## Reference Files

- `references/validation-criteria-requirements.md` — Per-section validation criteria for requirements.md
- `references/validation-criteria-ui-design.md` — Per-section validation criteria for ui-design.md
- `references/validation-criteria-design.md` — Per-section validation criteria for design.md
- `references/validation-criteria-tasks.md` — Per-section validation criteria for tasks.md
- `references/validation-criteria.md` — Validation criteria index (routes to per-doc files)
- `references/bug-fix-criteria.md` — Additional criteria for bug fix spec review
- `references/testing-coverage.md` — Testing coverage assessment criteria and tier 1 checks
- `references/cross-validation-criteria.md` — Spec-specific cross-document consistency pairs and checks
- `references/artifact-assessment-format.md` — Quality artifact JSON format for review output
