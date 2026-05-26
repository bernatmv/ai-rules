# Template Compliance Validation

Validates documents against their canonical templates. Referenced by all review skills.

## Contents
- [Procedure](#procedure)
- [Template Validation](#template-validation)
- [Variable Substitution Convention](#variable-substitution-convention)
- [If Templates Missing](#if-templates-missing)
- [Document ↔ Template Mappings](#document--template-mappings)

## Procedure

### Step 1: Load Canonical Template

**CLI resolution (preferred):**

```
.spec-workflow/sdd util/resolve-template.py --type {doc_type} [--spec-name NAME] [--content]
```

Returns JSON with `source` ("user" or "default"), `path`, and optionally `content` (with variables substituted). Priority order:

1. Check `.spec-workflow/user-templates/{type}-template.md` — if present, use it
2. Fall back to `.spec-workflow/templates/{type}-template.md`
3. If neither exists, exit 1 — skip template compliance (not an error)

### Step 2: Extract Template Sections

Parse the template's top-level headings (## level) as the expected section inventory.

### Step 3: Compare Against Document

| Check | Pass | Fail |
|-------|------|------|
| Section heading present in document | ✅ | ❌ Missing section: `{heading}` |
| Section has non-placeholder content | ✅ | ⚠️ Section appears to contain only template placeholder text |

### Step 4: Report

| Criterion | Evaluation |
|-----------|------------|
| **Section Coverage** | X/Y template sections present |
| **Extra Sections** | List any document sections not in template (🟢 — not an error, may be project-specific) |
| **Placeholder Detection** | Any sections still containing template placeholder text |

**Rating:** **Compliant** (all sections present, no placeholders) | **Partial** (missing 1–2 sections or has placeholders) | **Non-compliant** (missing 3+ sections)

**Programmatic check** (exact CLI signature — two positional arguments, no flags):

```
.spec-workflow/sdd review/check-template-compliance.py \
  {template-file} {document-file}
```

Exit 0 = compliant, exit 1 = partial/non-compliant, exit 2 = usage error.

## Template Validation

Validate user-customized templates before document authoring:

```bash
.spec-workflow/sdd util/manage-template.py validate {type}
.spec-workflow/sdd util/manage-template.py validate --all
```

Programmatic validation via `sdd_core/templates.py`:

```python
from sdd_core.templates import validate_template
result = validate_template(template_path, doc_type)
# result.valid, result.errors, result.warnings, result.sections_found
```

## Variable Substitution Convention

After resolving any template, always call `sdd_core.templates.substitute_variables()` with `get_default_variables(spec_name=spec_name, project_path=project_path)` to expand `{{...}}` placeholders before using the template as an authoring guide. For steering docs (no spec name), omit `spec_name`.

## If Templates Missing

Warn user. Offer to create document without template, or guide user to create templates directory.

## Document ↔ Template Mappings

### Steering Documents

| Document | Template File |
|----------|---------------|
| product.md | product-template.md |
| tech.md | tech-template.md |
| structure.md | structure-template.md |

### Spec Documents

| Document | Template File | Bug-Fix Variant |
|----------|---------------|-----------------|
| requirements.md | requirements-template.md | bug-fix-requirements-template.md |
| design.md | design-template.md | bug-fix-design-template.md |
| tasks.md | tasks-template.md | bug-fix-tasks-template.md |

### PRD Documents

| Document | Template File |
|----------|---------------|
| prd.md | prd-template.md |
