# Architecture Criteria

Evaluates adherence to documented architecture patterns from tech.md and structure.md.

For DIP (Dependency Inversion Principle) rationale, see `$SKILLS/sdd-common/references/general-principles.md`.

## Contents
- [Pattern Compliance](#1-pattern-compliance-techmd)
- [File Placement](#2-file-placement-structuremd)
- [Module Boundaries](#3-module-boundaries)
- [Dependency Injection](#4-dependency-injection)
- [Concurrency Patterns](#5-concurrency-patterns)
- [Refactoring Assessment](#6-refactoring-assessment)

---

## 1. Pattern Compliance (tech.md)

**Pass:**
- Follows tech.md patterns
- Architecture consistent with docs
- Deviations justified and documented

**Fail:**
- Using a different architecture pattern than tech.md specifies
- Direct dependencies instead of injection (when tech.md requires DI)
- Synchronous when tech.md expects async
- Legacy concurrency patterns when tech.md documents a modern approach

## 2. File Placement (structure.md)

**Pass:**
- Files in correct directories
- Module boundaries respected
- New files follow organization

**Fail:**
- File in wrong module
- New module without justification
- Files scattered across locations

## 3. Module Boundaries

**Pass:**
- Dependencies flow correctly
- No circular dependencies
- Only public interfaces accessed across modules

**Fail:**
- Circular imports
- Internal details accessed across modules
- Tight coupling between unrelated modules

## 4. Dependency Injection

**Pass:**
- Dependencies injected via constructor
- No hard-coded dependencies
- Follows project DI patterns

**Fail:**
- Singleton access instead of injection
- Hard-coded dependency creation
- Direct service instantiation

> Implementation check only. DIP rationale → Step 4g `[REQUIRED]`. See `$SKILLS/sdd-common/references/general-principles.md`.

## 5. Concurrency Patterns

**Pass:**
- Follows the concurrency model documented in tech.md
- UI updates on the appropriate thread per tech.md patterns
- Thread-safe data access

**Fail:**
- Blocking main/UI thread
- Missing thread-safety annotations required by tech.md
- Race conditions in shared state
- Using deprecated concurrency patterns when tech.md documents modern alternatives

## 6. Refactoring Assessment

Lightweight checks for non-spec code changes that involve restructuring. For spec-driven
refactoring, use `$SKILLS/sdd-common/references/refactoring-validation.md` instead.

**Pass:**
- Behavior preserved (no functional changes mixed with structural changes)
- Renamed symbols updated at all call sites
- Extracted modules/functions have clear single responsibility
- No dead code left behind after extraction

**Fail:**
- Behavioral changes bundled with refactoring (hard to review, risky)
- Partial renames (some call sites still use old name)
- Extracted code still coupled to original module via internals
- Unused imports, variables, or functions left after restructuring
