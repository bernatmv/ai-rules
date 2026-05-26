# Detection Rules


## Contents

- [Dynamic Document Validation](#dynamic-document-validation)
- [PRD Detection](#prd-detection)
- [Bug Fix Spec Detection](#bug-fix-spec-detection)

## Dynamic Document Validation

When reviewing document types without predefined criteria:

### Step 1: Check Template

Resolve template using priority order (see `template-compliance.md` § Step 1: Load Canonical Template):
1. `.spec-workflow/user-templates/[type]-template.md` (user override)
2. `.spec-workflow/templates/[type]-template.md` (workspace default)

### Step 2: Apply Universal Criteria

| Criterion | Evaluation |
|-----------|------------|
| **Completeness** | All sections filled meaningfully |
| **Clarity** | Understandable without additional context |
| **Actionability** | Provides enough detail to act on |
| **Consistency** | Terminology matches related docs |
| **Traceability** | Links to related documents |

### Step 3: Derive Section-Specific Criteria

For each template section, ask:
1. What is this section's purpose?
2. How would I verify it?
3. What indicates failure?

## PRD Detection

Keywords: "prd", "product requirements document", "product requirements",
"write a prd", "create prd"

Route to: sdd-create-prd

Disambiguation from spec: If user says "create spec" or
"requirements.md", route to sdd-create-spec. If user says
"create prd" or "product requirements document", route to
sdd-create-prd.

## Bug Fix Spec Detection

A spec is considered a **bug fix spec** if its name contains any of: `fix`, `bugfix`, `hotfix`, `patch`, `issue`.

**Programmatic check:** Run `../scripts/spec/detect-type.py <spec-name>` — outputs `bug-fix` or `standard`.

When detected:
- `sdd-review-spec-docs` also applies `bug-fix-criteria.md`
- `sdd-review-code` also loads `bug-fix-implementation-criteria.md`
- `sdd-create-spec` (bug-fix mode) uses `fix-{slug}` naming convention (the `fix-` prefix triggers detection in other skills)
