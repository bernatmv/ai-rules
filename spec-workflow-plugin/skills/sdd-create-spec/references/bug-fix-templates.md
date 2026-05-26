# Bug Fix Document Templates

Simplified template outlines for bug fix spec documents. These replace the full feature templates when creating specs under the `sdd-create-spec` bug-fix mode.

Documents still use standard filenames (`requirements.md`, `design.md`, `tasks.md`) for dashboard compatibility.

## Contents
- [Template ↔ Criteria Mapping](#template--criteria-mapping)
- [Bug Report Template (requirements.md)](#bug-report-template-requirementsmd)
- [Fix Design Template (design.md)](#fix-design-template-designmd)
- [Fix Tasks Template (tasks.md)](#fix-tasks-template-tasksmd)
- [Fast Path Task Reduction](#fast-path-task-reduction)
- [Fast Path Combined Review](#fast-path-combined-review)
- [Creation Summary Self-Check Templates](#creation-summary-self-check-templates)

---

## Template ↔ Criteria Mapping

Each template section maps to specific review criteria from `$SKILLS/sdd-review-spec-docs/references/bug-fix-criteria.md`. Writing to this mapping reduces first-pass review rejection.

### requirements.md Mapping

| Template Section | Review Criterion | Criteria Source |
|-----------------|------------------|-----------------|
| Bug Summary + Environment/Context + Current/Expected Behavior + Reproduction Steps | Technical Context Documents Issues | bug-fix-criteria.md §1 |
| Reproduction Steps | Reproduction Steps Actionable | bug-fix-criteria.md §1b |
| Scope Boundary + Severity/Impact | Issue Scope Bounded | bug-fix-criteria.md §2 |
| Traceability | Technical Context Documents Issues (traceability) | bug-fix-criteria.md §1 |
| Affected Components | Introduction Provides Clear Context (partial) | validation-criteria.md §1 |

### design.md Mapping

| Template Section | Review Criterion | Criteria Source |
|-----------------|------------------|-----------------|
| Root Cause Analysis + How Bug Was Introduced + Originating Spec Reference | Root Cause Analysis Present | bug-fix-criteria.md §1 |
| Fix Approach + Rejected Alternatives | Solution Addresses Root Cause | bug-fix-criteria.md §2 |
| Regression Risk Assessment + Regression Test Strategy | Regression Risk Assessed | bug-fix-criteria.md §3 |
| Fix Validation Plan | Fix Validation Plan Present | bug-fix-criteria.md §4 |

---

## Bug Report Template (requirements.md)

For the full template structure, see `.spec-workflow/templates/bug-fix-requirements-template.md` (or the reference copy at `$SKILLS/sdd-common/references/default-templates/bug-fix-requirements-template.md`).

---

## Fix Design Template (design.md)

For the full template structure, see `.spec-workflow/templates/bug-fix-design-template.md` (or the reference copy at `$SKILLS/sdd-common/references/default-templates/bug-fix-design-template.md`).

---

## Fix Tasks Template (tasks.md)

For the full template structure, see `.spec-workflow/templates/bug-fix-tasks-template.md` (or the reference copy at `$SKILLS/sdd-common/references/default-templates/bug-fix-tasks-template.md`).

Task 4 is optional — only include when the fix changes observable behavior documented elsewhere.

---

## Fast Path Task Reduction

When using the fast path (Critical/High severity), only these tasks are required:

| Task | Required |
|------|----------|
| 1. Apply fix | Always |
| 2. Add regression test(s) | Always — success criteria include: test fails when fix is reverted, reproduction steps from requirements.md no longer reproduce the bug |
| 3. Validate fix | **Included in task 2's success criteria** — additionally, agent must confirm reproduction steps pass post-fix before logging task as complete |
| 4. Update documentation | Omitted unless user explicitly requests |

---

## Fast Path Combined Review

When using the fast path (Critical/High severity), present both documents together for a single review pass. Both files are created separately for MCP compatibility, but shown to the user in this combined format:

```markdown
## Combined Review: Requirements + Design (fix-{slug})

**Severity:** [Critical/High] — Fast path review requested.
**Review both documents below. Approve or request revision for each.**

---

### Part 1: Bug Report (requirements.md)

[Full requirements.md content here]

---

### Part 2: Fix Design (design.md)

[Full design.md content here]

---

### Review Actions

For each document, indicate:
- ✅ **Approve** — Document meets criteria
- ⚠️ **Needs revision** — Specify what needs to change
- ❌ **Reject** — Specify fundamental issues

| Document | Decision | Notes |
|----------|----------|-------|
| requirements.md | [Approve / Needs revision / Reject] | |
| design.md | [Approve / Needs revision / Reject] | |
```

After the user responds, run `.spec-workflow/sdd approval/request.py` (one per file) with the appropriate action. If either document needs revision, revise it and re-present only the changed document for follow-up review.

---

## Creation Summary Self-Check Templates

After writing each document, follow the self-check process for that document.
Self-checks are agent-internal quality gates — do not present them to the user
as standalone output. Each row should show ✅ (pass) or ⚠️ (needs attention)
with a brief status note.

### requirements.md Self-Check

1. Run self-check:

   | Criterion (from bug-fix-criteria.md) | Self-Check |
   |---------------------------------------|------------|
   | Technical Context Documents Issues | ✅/⚠️ [Bug summary, reproduction, affected components present?] |
   | Reproduction Steps Actionable | ✅/⚠️ [Steps concrete, preconditions stated, expected vs actual clear?] |
   | Traceability | ✅/⚠️ [Originating spec documented or "N/A" with context?] |
   | Issue Scope Bounded | ✅/⚠️ [In-scope/out-of-scope defined?] |

2. If any check shows ⚠️, fix the document before proceeding.
3. **Approval gate** — run Review and Approval Pipeline. See SKILL.md § Pipeline Parameters (Step 4 row).

### design.md Self-Check

1. Run self-check:

   | Criterion (from bug-fix-criteria.md) | Self-Check |
   |---------------------------------------|------------|
   | Root Cause Analysis Present | ✅/⚠️ [Root cause, code-level detail, file references present?] |
   | Originating Spec Reference | ✅/⚠️ [Cross-reference present if applicable, or "N/A" with context?] |
   | Solution Addresses Root Cause | ✅/⚠️ [Fix targets cause not symptoms, explains resolution?] |
   | Regression Risk Assessed | ✅/⚠️ [Affected areas, regression scenarios, test strategy present?] |
   | Fix Validation Plan Present | ✅/⚠️ [Pre-fix baseline, post-fix verification, regression scope, automated validation?] |

2. If any check shows ⚠️, fix the document before proceeding.
3. **Approval gate** — run Review and Approval Pipeline. See SKILL.md § Pipeline Parameters (Step 8 row).

### tasks.md Self-Check

1. Run self-check:

   | Check | Self-Check |
   |-------|------------|
   | Tasks trace to requirements.md | ✅/⚠️ [Each task has `_Requirements:` reference] |
   | Tasks trace to design.md | ✅/⚠️ [Fix approach maps to task 1, test strategy maps to task 2] |
   | Success criteria are verifiable | ✅/⚠️ [Each `_Prompt: Success` is objectively testable] |

2. If any check shows ⚠️, fix the document before proceeding.
3. **Approval gate** — run Review and Approval Pipeline. See SKILL.md § Pipeline Parameters (Step 10 row).
