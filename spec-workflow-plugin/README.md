# spec-workflow-plugin

Spec-Driven Development (SDD) workflow skills for Claude Code and Cursor. Provides a complete lifecycle for requirements authoring, design documentation, implementation execution, and quality review — all guided by structured templates and approval gates.

## Prerequisites

- **Python 3.9+** — Required for SDD scripts
- **`.spec-workflow/sdd` shim** — Must be present in the target workspace. This shim invokes SDD Python scripts. See the [sdd-core-service](https://github.com/user/sdd-core-service) setup instructions for details.
- **Workspace structure** — SDD expects a `.spec-workflow/` directory in the project root with the runtime environment configured

## Install

### From ai-rules marketplace (this repo)

```sh
/plugin marketplace add bernatmv/ai-rules
/plugin install spec-workflow-plugin@ai-rules
/reload-plugins
```

### From agent-central-plugins (upstream)

```
/plugin marketplace add org-174376620@github.com:yahoo-common/agent-central-plugins.git
/plugin install spec-workflow-plugin@agent-central-plugins
/reload-plugins
```

### Alternative: CLI install

```bash
claude plugin add --from org-174376620@github.com:yahoo-common/agent-central-plugins.git --path spec-workflow-plugin
```

## Skills

### Development

| Skill | Description |
|-------|-------------|
| `sdd-create-discovery` | Scaffolds discovery projects and manifest metadata for the pre-spec phase |
| `sdd-create-prd` | Conversational PRD authoring with readiness gates, stress testing, and approval |
| `sdd-create-spec` | Phased spec creation (requirements, UI design, design, tasks) with template-guided authoring |
| `sdd-create-steering` | Authors project steering documents (product, tech, structure) with approval gates |
| `sdd-implement-spec` | Executes approved spec tasks with implementation logging and artifact tracking |

### Review

| Skill | Description |
|-------|-------------|
| `sdd-review-code` | Reviews code for quality, security, performance, conventions, and spec compliance |
| `sdd-review-prd` | Reviews PRD quality for problem clarity, goal measurability, and SDD readiness |
| `sdd-review-spec-docs` | Reviews spec documents for completeness, testing coverage, and cross-document consistency |
| `sdd-review-steering-docs` | Reviews steering documents for completeness, consistency, and project drift |

### Workflow

| Skill | Description |
|-------|-------------|
| `sdd-archive-spec` | Archives completed or abandoned specs with metadata |
| `sdd-manage-status` | Status dashboards, approval transitions, and task regeneration |
| `sdd-manage-template` | Template CRUD operations (list, preview, customize, validate, reset, diff, sync) |
| `sdd-workspace-create-spec` | Multi-repo spec coordination with central workspace tracking |

### Shared

| Skill | Description |
|-------|-------------|
| `sdd-common` | Internal dependency hub — shared references, scripts, and templates (not user-invocable) |

## Development

### Validate locally

```bash
pip install pyyaml

# Validate a single skill
python3 .github/scripts/validate_skill.py spec-workflow-plugin/skills/sdd-create-spec

# Validate all skills
for skill in spec-workflow-plugin/skills/sdd-*/; do
  python3 .github/scripts/validate_skill.py "$skill"
done
```

### Version management

The canonical version lives in `sdd_core/__init__.py` (`__version__`).
The `plugin.json` version must match — enforced by `scripts/util/check-version-sync.py`.

### Skill structure

Each skill contains:
- `SKILL.md` — Skill definition with YAML frontmatter and workflow instructions
- `references/` — Supporting documentation loaded on demand
- `scripts/` — Python scripts (in `sdd-common` only, invoked via `.spec-workflow/sdd`)

## Author

Membership Platforms — SDD Guild Team

## License

Apache-2.0
