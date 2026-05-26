# Code Quality Criteria

Evaluates code quality, readability, reuse, and adherence to coding standards.

DRY/SOLID principle evaluation → Step 4g `[REQUIRED]`. See `$SKILLS/sdd-common/references/general-principles.md`.

## Contents
- [Core Quality Checks](#core-quality-checks)
- [Reuse and DRY](#reuse-and-dry)
- [Anti-Pattern Taxonomy](#anti-pattern-taxonomy)

---

## Core Quality Checks

| # | Criterion | Pass | Fail |
|---|-----------|------|------|
| 1 | **Compilation/Syntax** | Compiles without errors; no syntax errors; all imports resolved | Compilation errors; missing imports; syntax errors |
| 2 | **Error Handling** | All paths handled; meaningful messages; no silent failures; follows project patterns | Unhandled errors; empty catches; generic messages; silent data corruption |
| 3 | **Naming Conventions** | Follows tech.md; descriptive names; consistent; matches codebase style | Inconsistent casing; cryptic abbreviations; names don't describe purpose |
| 4 | **Code Readability** | Self-documenting; complex logic commented; functions reasonably sized; clear control flow | Deep nesting; 50+ line functions; magic numbers; complex one-liners |
| 5 | **Documentation** | Public APIs documented; complex algorithms explained; README updated if needed | Public methods undocumented; complex code unexplained; outdated comments |

## Reuse and DRY

| # | Criterion | Pass | Fail |
|---|-----------|------|------|
| 6 | **No duplication** | No copy-paste; similar logic abstracted | Copy-pasted with minor variations; could have used existing utility |
| 7 | **Leverage references used** | Every `_Leverage:` reference used; referenced code imported and called correctly | Reference imported but not used; used incorrectly; ignored entirely |
| 8 | **Existing utilities discovered** | Similar functionality found and reused; common patterns use existing utilities; base classes extended | Reimplemented existing utility; copied instead of importing; custom solution when standard exists |
| 9 | **Pattern reuse** | Common patterns reused; follows established patterns from similar features | New pattern when existing fits; inconsistent vs similar features |

> DRY principle violations are also evaluated under `$SKILLS/sdd-common/references/general-principles.md`.
> This criteria evaluates the _implementation_ (did they reuse?); principles evaluate the _design_ (should they have?).

## Anti-Pattern Taxonomy

| Anti-Pattern | Detection | Severity |
|-------------|-----------|----------|
| God object/function | Single unit handling multiple unrelated concerns; >200 lines | High |
| Shotgun surgery | Small change requires edits in many unrelated files | High |
| Feature envy | Method uses another class's data more than its own | Medium |
| Primitive obsession | Using primitives instead of small domain objects | Medium |
| Dead code | Unreachable code, unused imports, commented-out blocks | Low |
| Magic numbers/strings | Literal values without named constants | Low |

Severity levels reference `$SKILLS/sdd-common/references/review-conventions.md`.
