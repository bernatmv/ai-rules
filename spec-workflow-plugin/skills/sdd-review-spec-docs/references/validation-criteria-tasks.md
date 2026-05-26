# tasks.md Validation Criteria

## Contents
- [Tasks Atomic and Actionable](#1-tasks-atomic-and-actionable)
- [File Paths Specified](#2-file-paths-specified)
- [Requirements Traceability Complete](#3-requirements-traceability-complete)
- [Code Reuse Documented](#4-code-reuse-documented)
- [Task Sequencing Respects Dependencies](#5-task-sequencing-respects-dependencies)
- [Implementation Prompts Well-Structured](#6-implementation-prompts-well-structured)
- [Testing Tasks Comprehensive](#7-testing-tasks-comprehensive)
- [Verification Tasks Cover Removal/Parity](#8-verification-tasks-cover-removalparity)
- [Task Lifecycle Suffix Valid](#9-task-lifecycle-suffix-valid-deterministic)

### 1. Tasks Atomic and Actionable

**Pass:**
- Each task is single, completable unit
- Descriptions clear and specific
- Developer can start from description alone
- Tasks appropriately sized
- Purpose statement explains why

**Fail:**
- Compound tasks (multiple unrelated changes)
- Vague ("implement feature")
- Requires additional clarification
- Spans multiple unrelated files
- Missing/unclear purpose

### 2. File Paths Specified

**Pass:**
- Each task specifies target file path(s)
- Paths follow project structure conventions
- New files in appropriate directories
- Modifications clearly identified

**Verification:** Paths align with structure.md

**Fail:**
- No file paths for implementation tasks
- Paths violate conventions
- Ambiguous ("somewhere in src/")

### 3. Requirements Traceability Complete

**Pass:**
- Each task has `_Requirements:` references
- All requirements have corresponding tasks
- References accurate and verifiable
- Enables coverage tracking

**Verification:** Map all `_Requirements:` back to requirements.md

**Deterministic check available:**

```bash
.spec-workflow/sdd spec/check-traceability.py --target {spec-name}
```

Run this first. The script reports uncovered requirements and orphan task references.
If it exits 0, traceability is complete. If it exits 1, report the specific gaps.

**Fail:**
- Tasks missing `_Requirements:`
- Orphan tasks without linkage
- Requirements without implementing tasks
- Incorrect references

### 4. Code Reuse Documented

**Pass:**
- Tasks include `_Leverage:` references
- Existing utilities/patterns identified
- `_Leverage:` matches design.md analysis
- Guidance on patterns to extend

**Verification:** Cross-reference with design.md code reuse analysis

**Fail:**
- Missing `_Leverage:` where reuse appropriate
- Reinventing functionality
- `_Leverage:` doesn't match design.md

### 5. Task Sequencing Respects Dependencies

**Pass:**
- Tasks numbered/ordered logically
- Dependencies clear ("continue from task 2")
- Foundation tasks before consuming tasks
- Parallel-safe tasks identifiable
- No circular dependencies

**Fail:**
- Tasks reference uncreated components
- Illogical ordering (tests before implementation)
- Implicit dependencies undocumented
- Foundation work buried in middle/end

### 6. Implementation Prompts Well-Structured

**Pass:**
- `_Prompt:` section with:
  - **Role**: Developer persona required
  - **Task**: Clear implementation description
  - **Restrictions**: Boundaries/constraints
  - **Success**: Measurable completion criteria
- Sufficient context for AI-assisted development
- Success criteria specific and verifiable

**Deterministic check available:**

```bash
.spec-workflow/sdd spec/lint-tasks.py --target {spec-name}
```

Run this once on the file. The script validates both prompt structure (Role, Task,
Restrictions, Success, canonical prefix) and lifecycle suffix (4 required keywords
in order, no contradictions). If it exits 0, criteria #6 and #9 are both satisfied.
If it exits 1, check stderr for per-task detail on what failed.

**Fail:**
- Missing `_Prompt:` sections
- Incomplete structure
- Vague success criteria ("it works")
- Restrictions contradict design.md

### 7. Testing Tasks Comprehensive

**Pass:**
- Dedicated testing tasks for each level
- Testing tasks follow implementation tasks
- Reference design.md test strategy
- Include: test file paths, components/flows, leverage refs, coverage expectations
- Cover all acceptance criteria

**Verification:** Map test tasks to design.md strategy and acceptance criteria

**Fail:**
- No testing tasks
- Vague ("write tests")
- Don't cover all levels from design.md
- Missing acceptance criteria coverage
- No leverage of existing test utilities

**Thoroughness:** Comprehensive (all levels, all criteria, leverages infrastructure) → Adequate (most levels) → Basic (unit only or generic) → Insufficient (none/vague)

### 8. Verification Tasks Cover Removal/Parity

**Pass:**
- Tasks include build/package verification
- Runtime smoke checks for removed behavior
- Scans for lingering references
- Migration verification for consumer apps

**Fail:**
- No dependency removal validation
- Only code changes, no verification
- Missing runtime checks or migration validation

### 9. Task Lifecycle Suffix Valid (Deterministic)

**Method:** Covered by the same `spec/lint-tasks.py` script as criterion #6. No separate step needed — if #6's deterministic check passed, #9 passes too.

**Pass:** Script exits 0 — all non-complete tasks have valid lifecycle suffix with 4 required keywords in correct order and no contradiction patterns.

**Fail:** Script exits 1 — report stderr output verbatim (it identifies which tasks fail and why).
