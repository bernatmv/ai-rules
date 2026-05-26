# Common Edge Cases

Shared edge case patterns referenced by multiple SDD skills. Skills should reference this file and only list skill-specific edge cases inline.


## Contents

- [Template Missing](#template-missing)
- [Approval Rejected](#approval-rejected)
- [Spec Not Found](#spec-not-found)
- [Resume Existing](#resume-existing)
- [Bug Fix Detection](#bug-fix-detection)
- [Project/Resource Already Exists](#projectresource-already-exists)
- [Template Validation Failed](#template-validation-failed)

## Template Missing

| Situation | Action |
|-----------|--------|
| Template file not found | Present `template-missing` prompt from registry via AskQuestion — user decides to proceed without template or cancel |

Applies to: sdd-create-spec, sdd-create-steering

## Approval Rejected

| Situation | Action |
|-----------|--------|
| Approval rejected | Read feedback, revise document, re-request approval. 3-cycle iteration limit per `approval-flow.md` § Iteration Limit. |

Applies to: sdd-create-spec, sdd-create-steering, sdd-manage-status

## Spec Not Found

| Situation | Action |
|-----------|--------|
| Spec not found | Report error: "Spec '{name}' not found." List available specs from `.spec-workflow/specs/`. |

Applies to: sdd-implement-spec, sdd-review-spec-docs, sdd-review-code, sdd-archive-spec, sdd-manage-status

## Resume Existing

| Situation | Action |
|-----------|--------|
| User resumes existing spec/steering | Run `.spec-workflow/sdd spec/check-status.py`, determine last completed step, resume from next incomplete step. |

Applies to: sdd-create-spec, sdd-create-steering, sdd-implement-spec

## Bug Fix Detection

Bug fix specs are detected per `detection-rules.md`:
- Name prefix: `fix-*`
- Keywords: "bug", "fix", "hotfix", "patch", "defect"

When detected, load bug-fix-specific criteria and templates.

Applies to: sdd-create-spec, sdd-review-spec-docs, sdd-review-code

## Project/Resource Already Exists

| Situation | Action |
|-----------|--------|
| Target project or resource already exists on create | Warn user, offer to resume instead of overwrite. |

Applies to: sdd-create-discovery

## Template Validation Failed

| Situation | Action |
|-----------|--------|
| User-template fails validation | Show errors and warnings. Suggest `sdd validate template {type}` to re-check or `sdd reset template {type}` to remove the override and revert to defaults. |

Applies to: sdd-manage-template, sdd-create-spec, sdd-create-steering
