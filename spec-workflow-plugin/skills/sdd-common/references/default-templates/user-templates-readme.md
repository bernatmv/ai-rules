# User Templates

Place custom templates here to override defaults.
Files here take priority over `.spec-workflow/templates/`.

## Supported Templates

- requirements-template.md
- design-template.md
- tasks-template.md
- product-template.md
- tech-template.md
- structure-template.md
- bug-fix-requirements-template.md
- bug-fix-design-template.md
- bug-fix-tasks-template.md

## Template Variables

Templates support `{{variable}}` placeholders that are replaced during
document authoring. **Only the following variables are recognized** — any
other `{{...}}` syntax will trigger a validation warning:

| Variable | Source | Example |
|----------|--------|---------|
| `{{projectName}}` | Directory name of project root | `sdd-core-service` |
| `{{featureName}}` | Spec name (kebab-case) | `user-authentication` |
| `{{specName}}` | Alias for `featureName` | `user-authentication` |
| `{{date}}` | Current date (ISO 8601) | `2026-03-23` |
| `{{author}}` | Git user.name (fallback: `"unknown"`) | `J. Guo` |

## Validate Your Template

After creating or editing a custom template, validate it:

    sdd validate template {type}

Validation checks for structural requirements (headings, sections),
recognized variables, and security (no raw HTML). Fix any errors before
using the template for document authoring.

## Getting Started

1. `sdd customize template {type}` — copies the default to this directory
2. Edit the file to suit your project
3. `sdd validate template {type}` — check for issues
4. `sdd diff template {type}` — compare your version to the default
