# Refactoring Validation

Shared checklists for reviewing refactoring specs and implementations.
Apply the appropriate lens depending on the review context.


## Contents

- [Approach Selection](#approach-selection)
- [Objectives-Based Validation](#objectives-based-validation)
- [Function Parity Validation](#function-parity-validation)
- [Dependency Removal (when applicable)](#dependency-removal-when-applicable)

## Approach Selection

If requirements.md explicitly states refactoring objectives → **Objectives-Based**.
Otherwise → **Function Parity** (fallback).

## Objectives-Based Validation

### Spec Review (document quality)

| Criterion | Pass/Fail |
|-----------|-----------|
| Each objective explicit and measurable | |
| Design addresses each objective | |
| Tasks trace to objectives via `_Requirements:` | |
| Verification tasks validate objectives | |

### Implementation Review (code quality)

| Criterion | Pass/Fail |
|-----------|-----------|
| Each objective achieved in implementation | |
| Approach matches design.md strategy | |
| Success criteria demonstrably met | |
| Trade-offs acceptable per design.md | |
| Verification tests confirm objectives | |

## Function Parity Validation

### Spec Review (document quality)

| Criterion | Pass/Fail |
|-----------|-----------|
| Public API behavior documented | |
| Error handling consistency specified | |
| Performance expectations documented | |
| Integration points identified | |
| Test coverage verifies parity | |

### Implementation Review (code quality)

| Criterion | Pass/Fail |
|-----------|-----------|
| Public API behavior preserved | |
| Error handling consistent | |
| Edge cases behave identically | |
| Performance maintained/improved | |
| Integration points unchanged | |

## Dependency Removal (when applicable)

### Spec Review (document quality)

| Criterion | Document | Pass/Fail |
|-----------|----------|-----------|
| Behavior parity explicitly stated | requirements.md | |
| Trade-offs documented | requirements.md + design.md | |
| New source of truth defined | design.md | |
| Removal verification tasks exist | tasks.md | |

### Implementation Review (code quality)

| Criterion | Pass/Fail |
|-----------|-----------|
| Old dependency completely removed | |
| Build succeeds without it | |
| All functionality replaced | |
| New implementation follows design.md | |
| No regressions detected | |
