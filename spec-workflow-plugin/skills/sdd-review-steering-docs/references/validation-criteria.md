# Steering Document Validation Criteria

Per-document criteria are split into focused files for selective loading.
Load only the file(s) needed for the current review scope.

| Document | Criteria File |
|----------|--------------|
| product.md | `validation-criteria-product.md` |
| tech.md | `validation-criteria-tech.md` |
| structure.md | `validation-criteria-structure.md` |

## Cross-Document Validation

See `cross-validation-criteria.md` for duplication, conflict, gap, and drift detection
across the three steering docs (applies the framework from `$SKILLS/sdd-common/references/cross-validation.md`).

## Drift Detection Criteria

For drift detection workflow and severity classifications, see `drift-detection.md`.

## Codebase Verification

Always verify steering docs against actual code:

| Verification | Method |
|--------------|--------|
| Tech stack | Check dependency manifests |
| Structure | Run `ls` on key directories |
| Patterns | Spot-check source files |
