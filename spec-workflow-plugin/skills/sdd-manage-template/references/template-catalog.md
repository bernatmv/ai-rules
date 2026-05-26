# Template Catalog

Canonical inventory of all SDD templates with descriptions and usage context.
For normative document ↔ template mappings, see `$SKILLS/sdd-common/references/template-compliance.md` § Document ↔ Template Mappings.

## Standard Templates (Feature Specs)

| Template | File | Purpose |
|----------|------|---------|
| Requirements | `requirements-template.md` | Feature requirements with user stories, acceptance criteria, and non-functional requirements |
| Design | `design-template.md` | Architecture, components, data models, error handling, and testing strategy |
| Tasks | `tasks-template.md` | Implementation task list with file paths, leverage notes, requirements tracing, and _Prompt suffixes |

## Standard Templates (Steering Docs)

| Template | File | Purpose |
|----------|------|---------|
| Product | `product-template.md` | Product vision, target users, key features, business objectives, and success metrics |
| Tech | `tech-template.md` | Technology stack, development environment, deployment, and technical decisions |
| Structure | `structure-template.md` | Directory organization, naming conventions, import patterns, and code size guidelines |

## Bug-Fix Templates

| Template | File | Purpose |
|----------|------|---------|
| Bug Report | `bug-fix-requirements-template.md` | Bug summary, reproduction steps, severity, traceability, and scope boundary |
| Fix Design | `bug-fix-design-template.md` | Root cause analysis, fix approach, regression risk, and validation plan |
| Fix Tasks | `bug-fix-tasks-template.md` | Fix implementation, regression tests, validation, and documentation tasks |

## Workspace Templates

| Template | File | Purpose |
|----------|------|---------|
| Workspace Requirements | `workspace-requirements-template.md` | Standard requirements + `Cross-Repo Scope` table + optional `Open Questions` section. Used by `sdd-workspace-create-spec` for the coordinator repo's requirements.md. |

## Template Locations

| Location | Purpose | Auto-Updated |
|----------|---------|:------------:|
| `$SKILLS/sdd-common/references/default-templates/` | Source of truth (version-controlled) | No |
| `.spec-workflow/templates/` | Workspace defaults (copied on init/sync) | Yes |
| `.spec-workflow/user-templates/` | User overrides (take priority) | Never |

## Template Variables

Templates support `{{variable}}` placeholders replaced during document authoring.

| Variable | Source | Example |
|----------|--------|---------|
| `{{projectName}}` | Directory name of project root | `sdd-core-service` |
| `{{featureName}}` | Spec name (kebab-case) | `user-authentication` |
| `{{specName}}` | Alias for `featureName` | `user-authentication` |
| `{{date}}` | Current date (ISO 8601) | `2026-03-23` |
| `{{author}}` | Git user.name (fallback: `"unknown"`) | `J. Guo` |

## Resolution Order

When a skill needs a template, resolution follows this priority:

1. `.spec-workflow/user-templates/{type}-template.md` — user override
2. `.spec-workflow/templates/{type}-template.md` — workspace default
3. `None` — caller decides fallback behavior
