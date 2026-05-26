# Spec Document Validation Criteria

Per-document criteria are split into focused files for selective loading.
Load only the file(s) needed for the current review scope.

| Document | Criteria File |
|----------|--------------|
| requirements.md | `validation-criteria-requirements.md` |
| design.md | `validation-criteria-design.md` |
| tasks.md | `validation-criteria-tasks.md` |

## Refactoring Validation (when applicable)

Apply the checklists from `$SKILLS/sdd-common/references/refactoring-validation.md` using the
**Spec Review** lens. Choose Objectives-Based or Function Parity per the
approach selection rules in that file.
