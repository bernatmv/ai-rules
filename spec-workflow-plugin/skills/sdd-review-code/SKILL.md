---
name: sdd-review-code
description: Reviews code for quality, security, performance, conventions, and spec
  compliance. Supports standalone review (any code changes) and spec-aware review
  (SDD implementation). Use when asked to review code, review implementation, check
  code quality, review changes, review PR, or run code review.
allowed-tools: Read Write Edit Bash Agent AskQuestion AskUserQuestion TaskCreate TaskUpdate WebFetch
metadata:
  version: 3.3.1
  category: review
  dependencies: [sdd-common]
  author: membership-platforms-sdd-guild
---

> **Paths:** See `$SKILLS/sdd-common/references/path-conventions.md`. Scripts: `.spec-workflow/sdd {group}/{script}.py`.

# SDD: Review Code

Reviews code for quality, security, performance, conventions, and spec compliance.
Two modes: **standalone** (any code changes) and **spec-aware** (SDD implementation).

Severity, scoring, and report conventions: see `$SKILLS/sdd-common/references/review-conventions.md`.

## Contents

- [Dependencies](#dependencies)
- [Invocation Examples](#invocation-examples)
- [Workflow](#workflow)
- [Workflow Progress](#workflow-progress)
- [Safety Rules](#safety-rules)
- [Edge Cases](#edge-cases)
- [Logging Implementation (After Review)](#logging-implementation-after-review)
- [Human approval ceremony](#human-approval-ceremony)
- [Completion](#completion)
- [Reference Files](#reference-files)

## Dependencies

> Load each criteria file only at the start of its dimension step. Record the dimension result BEFORE reading the next criteria file. Freedom legend: see `$SKILLS/sdd-common/references/freedom-column.md`.

| Step | File | Kind | Freedom |
|------|------|------|:-:|
| Step 0 (spec-aware) | `$SKILLS/sdd-common/references/tool-patterns.md` (spec/check-status.py) | read | L |
| Step 3 | `$SKILLS/sdd-review-code/references/criteria-conventions.md` (convention discovery protocol) | read | H |
| Step 4a | `$SKILLS/sdd-review-code/references/criteria-code-quality.md` | read | H |
| Step 4b | `$SKILLS/sdd-review-code/references/criteria-architecture.md` | read | H |
| Step 4c | `$SKILLS/sdd-review-code/references/criteria-security.md` | read | H |
| Step 4d | `$SKILLS/sdd-review-code/references/criteria-performance.md` | read | H |
| Step 4e | `$SKILLS/sdd-review-code/references/criteria-testing.md` | read | H |
| Step 4f | `$SKILLS/sdd-review-code/references/criteria-conventions.md` (convention checks) | read | H |
| Step 4g | `$SKILLS/sdd-common/references/general-principles.md` | read | H |
| Step 4h | `$SKILLS/sdd-review-code/references/criteria-design-drift.md` (conditional: frontend files) | read | H |
| Step 4i | `$SKILLS/sdd-review-code/references/platform-criteria.md` (conditional: per tech.md) | read | H |
| Step 5 (spec-aware) | `$SKILLS/sdd-review-code/references/criteria-task-compliance.md` | read | M |
| Step 5b (spec-aware) | `$SKILLS/sdd-common/references/template-compliance.md` | read | M |
| Step 5c (spec-aware + bug fix) | `$SKILLS/sdd-review-code/references/bug-fix-implementation-criteria.md` | read | M |
| Step 5d (spec-aware + refactoring) | `$SKILLS/sdd-common/references/refactoring-validation.md` | read | M |
| Step 6 | `$SKILLS/sdd-review-code/references/report-template.md` | read | L |
| Step 6 | `$SKILLS/sdd-common/references/review-conventions.md` | read | L |
| Step 7 | `$SKILLS/sdd-common/references/review-approval-pipeline.md` (§ Fix-Loop) | read | L |
| Step 7 | `$SKILLS/sdd-common/references/fix-loop-protocol.md` | read | L |
| Conditional | `$SKILLS/sdd-common/references/detection-rules.md` (bug fix detection) | read | M |
| Conditional | `$SKILLS/sdd-common/references/telemetry.md` (after review, logging) | read | L |
| All | `$SKILLS/sdd-common/references/state-scope.md` (scope + lifetime of persisted state) | read | L |

## Invocation Examples

| Request | Mode | Action |
|---------|------|--------|
| `sdd review code` | Standalone | Review uncommitted/staged changes |
| `sdd review changes [base..head]` | Standalone | Review git range |
| `sdd review implementation [name]` | Spec-aware | Review all implemented tasks |
| `sdd review task [task-id] [name]` | Spec-aware | Review specific task |
| `sdd review PR` | Standalone | Review current branch changes |

## Workflow

### Step 0: Determine Mode and Check Prerequisites

**Mode detection:**

| Signal | Mode |
|--------|------|
| Spec name provided (`review implementation [name]`, `review task [id] [name]`) | Spec-aware |
| No spec name (`review code`, `review changes`, `review PR`) | Standalone |

**Spec-aware prerequisites** — use the spec-status check pattern from `$SKILLS/sdd-common/references/tool-patterns.md`:

| Phase | Required Status |
|-------|-----------------|
| Requirements | `approved` |
| Design | `approved` |
| Tasks | `approved` |
| Implementation | `in_progress` or `completed` |

If not met, guide user to complete earlier phases first.

**Standalone prerequisites** — none. Proceed directly.

### Step 1: Load Context

**Spec-aware mode:**

1. **tasks.md**: Task definitions, status markers, `_Requirements:`, `_Leverage:`, `_Prompt:` references
2. **design.md**: Architecture decisions, code reuse analysis, testing strategy
3. **requirements.md**: Acceptance criteria, non-functional requirements
4. **Steering docs**: tech.md (patterns), structure.md (file organization)

Identify refactoring specs: look for `refactor`, `replace`, `remove`, `migrate`, `consolidate`, `restructure` in spec name or requirements.md.

Identify bug fix specs: per `$SKILLS/sdd-common/references/detection-rules.md`.

**Standalone mode:**

1. **tech.md** and **structure.md** if available (for architecture/convention context)
2. If no steering docs exist, proceed without — conventions will be auto-discovered in Step 3

### Step 2: Gather Evidence

**Primary — git diff:**

```bash
# Standalone: uncommitted changes
git diff --name-only
git diff --staged --name-only

# Standalone with range: specific commits
git diff --name-only {base}...{head}

# Spec-aware: changes since main
git diff --name-only main...HEAD
git diff main...HEAD -- [relevant-paths]
```

**Fallback chain (spec-aware):**

1. Implementation logs in `.spec-workflow/specs/{spec-name}/Implementation Logs/`
2. Read modified files directly based on tasks.md paths

Build a file inventory: list of all changed files with change type (added/modified/deleted).

### Step 3: Discover Conventions

Read `references/criteria-conventions.md` and follow its discovery protocol.

Non-negotiables for this step:

1. Read at least one config file for the changeset's file types (`.eslintrc*`, `tsconfig.json`, `.prettierrc*`, etc.). If none exists, document the absence.
2. For each distinct file type in the changeset, read 2-3 sibling files.
3. Record discovered conventions as a summary before proceeding to Step 4.

If no sibling files exist for a file type, note this explicitly and skip convention checks for that type.

### Step 4: Apply Review Dimensions

Evaluate each dimension by reading its criteria file on demand. Skip conditional dimensions when inapplicable.

**4a: Code Quality** `[REQUIRED]` — Read `references/criteria-code-quality.md`. Evaluate core quality checks, reuse/DRY, and anti-patterns.

**4b: Architecture** `[REQUIRED]` — Read `references/criteria-architecture.md`. Evaluate pattern compliance, file placement, module boundaries, DI, concurrency.

**4c: Security** `[REQUIRED]` — Read `references/criteria-security.md`. Always evaluated. Evaluate OWASP-aligned checklist. Load cloud security section only if tech.md mentions cloud providers.

**4d: Performance** `[REQUIRED]` — Read `references/criteria-performance.md`. Evaluate algorithmic efficiency, database access, caching, bundle/assets, concurrency, memory, rendering.

**4e: Testing** `[REQUIRED]` — Read `references/criteria-testing.md`. Evaluate coverage checks and apply coverage gap methodology.

**4f: Conventions** `[REQUIRED]` — Read `references/criteria-conventions.md`. Compare changed files against conventions discovered in Step 3.

**4g: General Principles** `[REQUIRED]` — Apply code-level checks from `$SKILLS/sdd-common/references/general-principles.md`. Use the override mechanism if user supplies custom principles. Generate a principle scorecard table.

**4h: Design Drift** `[CONDITIONAL]` — Read `references/criteria-design-drift.md`. Load only when changed files include frontend/UI code. Skip if no frontend files in the change set.

**4i: Platform** `[CONDITIONAL]` — Read `references/platform-criteria.md`. Load only when tech.md documents platform-specific patterns. Derive all checks from steering docs.

### Step 5: Spec-Aware Dimensions (skip in standalone mode)

**5a: Task Compliance** — Read `references/criteria-task-compliance.md`. For each task, verify file paths, purpose achievement, requirements traceability, leverage utilization, success criteria, and restrictions.

Build a task completion matrix:

| Task ID | Description | Status | Files | Notes |
|---------|-------------|--------|-------|-------|
| 1 | [desc] | [x]/[-]/[ ] | [path] | |

**5b: Template Compliance** — Apply template compliance per `$SKILLS/sdd-common/references/template-compliance.md`. If any spec doc is non-compliant, flag as Warning — implementation may be correct but built against outdated spec structure.

**5c: Bug Fix Validation** (conditional) — If bug fix spec detected, read `references/bug-fix-implementation-criteria.md`. Evaluate root cause fix, regression tests, scope containment.

**5d: Refactoring Validation** (conditional) — If refactoring spec detected, apply checklists from `$SKILLS/sdd-common/references/refactoring-validation.md` using the Implementation Review lens.

### Step 6: Generate Report

Generate report per `references/report-template.md`. Severity and scoring per `$SKILLS/sdd-common/references/review-conventions.md`.

Report includes:
1. Executive summary (2-3 sentences)
2. Overall status (PASS / NEEDS WORK / FAIL)
3. Dimension scorecards (score + status per dimension)
4. Principle Scorecard (SOLID + DRY/KISS/YAGNI with per-principle evidence)
5. Anti-Pattern Checks (per `references/criteria-code-quality.md § Anti-Pattern Taxonomy`)
6. Findings ordered by severity (Critical first)
7. Positive observations (3-5 things done well)

For partial implementations (spec-aware), add a Progress Report section with completed/in_progress/pending task tables.

**Post-report validation** — After generating the report, run:
`.spec-workflow/sdd review/validate-review-report.py --report report.md`
If validation fails, fix the report and re-run until it passes.

### Step 7: Fix Loop

Read `$SKILLS/sdd-common/references/fix-loop-protocol.md` and execute its
**Mandatory Execution Checklist** step by step. Track progress using the TODO encoding from fix-loop-protocol.md § TODO Encoding.

**TODO lifecycle:** When entering the fix loop, mark `step7` as
`cancelled` (replaced by cycle-level TODOs). If the review passes
with zero findings, mark `step7` as `completed` and skip cycle TODOs.

**Hard constraints:**
- RE-VALIDATE — verify fixes produced changes via `git diff --stat`.
- RE-REVIEW — re-run Step 4 (scoped to affected dimensions + Conventions) after verifying fixes.
- Never report "0 issues found" without performing RE-VALIDATE and RE-REVIEW.

**AskQuestion format** — use the exact template from `$SKILLS/sdd-common/references/fix-loop-protocol.md § Prompt Structure`; field IDs, severity vocabulary, and option structure are fixed and all fields are required.

## Workflow Progress

**You MUST track progress using this checklist.** Do NOT proceed to Step 6 until all `[REQUIRED]` items are checked.

```
- [ ] Step 0: Determine mode + check prerequisites
- [ ] Step 1: Load context (spec docs or steering docs)
- [ ] Step 2: Gather evidence (git diff primary)
- [ ] Step 3: Discover conventions (config files + sibling files)
- [ ] Step 4: Apply review dimensions
  - [ ] 4a: Code Quality
  - [ ] 4b: Architecture
  - [ ] 4c: Security
  - [ ] 4d: Performance
  - [ ] 4e: Testing
  - [ ] 4f: Conventions
  - [ ] 4g: General Principles
  - [ ] 4h: Design Drift (if frontend files)
  - [ ] 4i: Platform (if tech.md specifies)
- [ ] Step 5: Spec-aware dimensions (if spec-aware mode)
  - [ ] 5a: Task Compliance
  - [ ] 5b: Template Compliance
  - [ ] 5c: Bug Fix Validation (if bug fix)
  - [ ] 5d: Refactoring Validation (if refactoring)
- [ ] Step 6: Generate report
- [ ] Step 7: Fix loop (max 2 cycles)
```

After completing each dimension in Steps 4a–4g, run:
`.spec-workflow/sdd review/validate-review-progress.py --phase record --dimension {dim_key} --read-file --checks-cited N`

After Step 3 (convention discovery), run:
`.spec-workflow/sdd review/validate-review-progress.py --phase conventions --summary "..."`

Before Step 6 (report generation), run:
`.spec-workflow/sdd review/validate-review-progress.py --phase check`
If validation fails, complete the missing dimensions.

After generating the report in Step 6, run:
`.spec-workflow/sdd review/validate-review-report.py --report report.md`

## Safety Rules

See `$SKILLS/sdd-common/references/review-safety-rules.md` for shared rules.

Skill-specific:
- In spec-aware mode, verify spec documents are approved before proceeding

## Edge Cases

See `$SKILLS/sdd-common/references/common-edge-cases.md` for shared patterns (Spec Not Found, Resume Existing). Skill-specific edge cases:

| Situation | Action |
|-----------|--------|
| No git changes detected | Ask user for file paths or commit range |
| Large diff (50+ files) | Ask user to scope: suggest focusing on highest-risk files (security-sensitive, new modules, API changes). If user confirms "review all", prioritize Critical/High findings and cap report to top 20 issues. |
| Standalone mode, no steering docs | Proceed without — rely on convention auto-discovery |
| Spec-aware mode, docs not approved | Report which docs need approval, suggest action |
| No sibling files for convention discovery | Skip convention check for that file type |
| All dimensions pass | Report PASS, mark `step7` as completed, skip fix loop |
| Fix loop introduces additional or regressive failures | Stop fixing, present failures, report NEEDS WORK |
| Reviewing remote PR (not checked out) | Use `fix-action-readonly` prompt; offer checkout-and-fix or skip |
| Conditional dimension skipped | Note the skip reason in the report for each skipped dimension |

Invocation for the `fix-action-readonly` prompt:

```
.spec-workflow/sdd util/generate-prompt.py --type fix-action-readonly
```

## Logging Implementation (After Review)

Apply the **Implementation Telemetry Logging** reference from `$SKILLS/sdd-common/references/telemetry.md` — it defines the workflow sequence, pre-implementation search, artifact requirements, `log-implementation.py` format, and artifact field reference.

**Skill-specific guidance:**
- `specName`: The spec name (e.g., `"user-auth"`)
- `summary`: Brief description of the feature implemented

See `$SKILLS/sdd-common/references/telemetry.md` for the full artifact schema and field reference.

## Human approval ceremony

Follow [`human-approval-ceremony.md`]($SKILLS/sdd-common/references/human-approval-ceremony.md) with `target_label="{spec-name}"` before any `.spec-workflow/sdd approval/update-status.py … approve`.

## Completion

Code review complete. Next step depends on what shipped: open or land the PR and address any non-blocking advisories. Once the spec is fully complete, archival is optional via `sdd archive {spec-name}`.

## Reference Files

- Code quality criteria: references/criteria-code-quality.md
- Architecture criteria: references/criteria-architecture.md
- Security criteria: references/criteria-security.md
- Performance criteria: references/criteria-performance.md
- Testing criteria: references/criteria-testing.md
- Convention criteria: references/criteria-conventions.md
- Design drift criteria: references/criteria-design-drift.md
- Task compliance criteria: references/criteria-task-compliance.md
- Report template: references/report-template.md
- Fix loop protocol: $SKILLS/sdd-common/references/fix-loop-protocol.md
- Bug fix implementation criteria: references/bug-fix-implementation-criteria.md
- Platform criteria: references/platform-criteria.md
- General principles: $SKILLS/sdd-common/references/general-principles.md
- Review conventions (severity, scoring, report): $SKILLS/sdd-common/references/review-conventions.md
- Template compliance: $SKILLS/sdd-common/references/template-compliance.md
- Refactoring validation: $SKILLS/sdd-common/references/refactoring-validation.md
- Tool patterns: $SKILLS/sdd-common/references/tool-patterns.md
- Detection rules: $SKILLS/sdd-common/references/detection-rules.md
- Telemetry logging: $SKILLS/sdd-common/references/telemetry.md
