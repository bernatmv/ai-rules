# ai-rules

A curated **Claude Code** plugin marketplace: skills, bundled official and third-party plugins, and MCP integrations for everyday engineering workflows.

## Plugins

| Plugin                                         | Description                                                                                     |
| ---------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| [fullstack-plugin](./fullstack-plugin)         | **Recommended** — bundles `core-plugin`, `frontend-plugin`, and `devops-plugin`                 |
| [core-plugin](./core-plugin)                   | Core skills plus engineering workflows, GitHub/Jira/Notion, documents, and productivity plugins |
| [frontend-plugin](./frontend-plugin)           | Frontend design, Figma, Playwright, Chrome DevTools, web assets, and Astro docs MCP             |
| [devops-plugin](./devops-plugin)               | Supabase and Vercel MCP integrations                                                            |
| [spec-workflow-plugin](./spec-workflow-plugin) | Spec-Driven Development (SDD) — spec creation, review, implementation, and workflow management  |

See [Installation](#installation) below, [`.claude/PLUGIN.md`](.claude/PLUGIN.md) for dependency details, and [`.claude/MCP.md`](.claude/MCP.md) for MCP setup.

## Plugin contents

### fullstack-plugin

Meta-plugin with no bundled skills. Depends on `core-plugin`, `frontend-plugin`, and `devops-plugin` — one install for the full stack.

### core-plugin

#### Bundled skills

| Skill             | Purpose                                                           |
| ----------------- | ----------------------------------------------------------------- |
| `babysit-pr`      | Keep a PR merge-ready: triage comments, resolve conflicts, fix CI |
| `launch-playbook` | Multi-platform product launch campaigns (56 platforms)            |
| `plugin-advisor`  | Recommend Claude Code plugins for a codebase                      |
| `prd`             | Generate product requirements documents                           |
| `ralph`           | Convert PRDs to `prd.json` for Ralph autonomous runs              |

TDD, planning, debugging, and code review workflows come from the `superpowers` dependency (`/superpowers:test-driven-development`, etc.) — not duplicated in this repo.

PDF and skill authoring come from dependency plugins (`document-skills`, `skill-creator`).
Autonomous Ralph execution comes from the `ralph-loop` dependency (`/ralph-loop`).

#### Dependencies (16)

| Plugin               | Purpose                                                       |
| -------------------- | ------------------------------------------------------------- |
| `superpowers`        | Development workflows (TDD, planning, debugging, code review) |
| `code-review`        | PR and code review agents                                     |
| `code-simplifier`    | Code simplification workflows                                 |
| `github`             | GitHub MCP                                                    |
| `ralph-loop`         | Autonomous iteration loop (`/ralph-loop`)                     |
| `atlassian`          | Jira and Confluence MCP                                       |
| `gitlab`             | GitLab MCP                                                    |
| `stripe`             | Stripe MCP                                                    |
| `huggingface-skills` | Hugging Face Hub skills and MCP                               |
| `skill-creator`      | Create and improve agent skills                               |
| `notion`             | Notion MCP                                                    |
| `document-skills`    | Excel, Word, PowerPoint, PDF processing                       |
| `claude-mem`         | Persistent memory across sessions                             |
| `visual-explainer`   | HTML diagrams, diff reviews, plan reviews                     |
| `jean-claude`        | Gmail, Google Drive, and Google Calendar (OAuth)              |
| `excalidraw-plugin`  | Excalidraw diagram JSON (ai-rules)                            |

#### MCP in core-plugin

| Server   | Purpose            |
| -------- | ------------------ |
| `convex` | Convex backend MCP |

### frontend-plugin

#### Dependencies (9)

| Plugin                         | Purpose                                             |
| ------------------------------ | --------------------------------------------------- |
| `frontend-design`              | Frontend UI design guidance                         |
| `playwright`                   | Playwright MCP for browser automation               |
| `figma`                        | Figma MCP and design workflow skills                |
| `chrome-devtools-mcp`          | Chrome DevTools MCP                                 |
| `web-asset-generator`          | Favicons, app icons, Open Graph images              |
| `vercel`                       | shadcn, Next.js best practices, Vercel agent skills |
| `browser-use-plugin`           | Browser automation CLI (ai-rules)                   |
| `remotion-plugin`              | Programmatic video creation (ai-rules)              |
| `app-store-screenshots-plugin` | App Store marketing screenshots (ai-rules)          |

#### MCP in frontend-plugin

| Server       | Purpose                    |
| ------------ | -------------------------- |
| `astro-docs` | Astro documentation search |

### devops-plugin

#### Dependencies (2)

| Plugin     | Purpose                                                          |
| ---------- | ---------------------------------------------------------------- |
| `supabase` | Supabase MCP integration                                         |
| `vercel`   | Vercel MCP plus Vercel agent skills (`vercel-labs/agent-skills`) |

### spec-workflow-plugin

Spec-Driven Development (SDD) lifecycle skills. Requires **Python 3.9+** and a `.spec-workflow/` workspace with the SDD runtime shim — see [spec-workflow-plugin/README.md](./spec-workflow-plugin/README.md).

| Category    | Skills                                                                                                   |
| ----------- | -------------------------------------------------------------------------------------------------------- |
| Development | `sdd-create-discovery`, `sdd-create-prd`, `sdd-create-spec`, `sdd-create-steering`, `sdd-implement-spec` |
| Review      | `sdd-review-code`, `sdd-review-prd`, `sdd-review-spec-docs`, `sdd-review-steering-docs`                  |
| Workflow    | `sdd-archive-spec`, `sdd-manage-status`, `sdd-manage-template`, `sdd-workspace-create-spec`              |
| Shared      | `sdd-common` (internal reference hub, not user-invocable)                                                |

## What lives here

| Path                                                                         | Role                                                     |
| ---------------------------------------------------------------------------- | -------------------------------------------------------- |
| [`CLAUDE.md`](CLAUDE.md)                                                     | Agent behavioral guidelines (Karpathy-style rules)       |
| [`AGENTS.md`](AGENTS.md)                                                     | Duplicate of `CLAUDE.md` for tools that read `AGENTS.md` |
| [`.claude/`](.claude/)                                                       | Claude Code hooks, settings, and plugin notes            |
| [`docs/`](docs/)                                                             | Reference material (e.g. Claude layout diagrams)         |
| [`core-plugin/`](core-plugin/), [`frontend-plugin/`](frontend-plugin/), etc. | Plugin packages published via this marketplace           |

## Installation

Requires **Claude Code v2.1.110+** (plugin dependencies). **v2.1.143+** recommended so dependency plugins enable automatically.

**Prerequisite for Google Workspace:** install [uv](https://docs.astral.sh/uv/) before using the `jean-claude` dependency (via `core-plugin` or `fullstack-plugin`).

**Prerequisite for SDD:** Python 3.9+ and `.spec-workflow/` workspace setup (via `spec-workflow-plugin`).

### Global install (recommended)

Use this when you want plugins available in **every project** on your machine (user scope).

Run once from any directory:

```sh
# 1. Third-party marketplaces (one-time; required by core-plugin and frontend-plugin)
/plugin marketplace add alonw0/web-asset-generator
/plugin marketplace add anthropics/skills
/plugin marketplace add thedotmack/claude-mem
/plugin marketplace add nicobailon/visual-explainer
/plugin marketplace add max-sixty/jean-claude

# 2. ai-rules marketplace
/plugin marketplace add bernatmv/ai-rules

# 3. Install (pick one approach)
/plugin install fullstack-plugin@ai-rules          # full stack — recommended
/plugin install spec-workflow-plugin@ai-rules      # optional: SDD workflow

# Or install individual plugins instead of fullstack-plugin:
# /plugin install core-plugin@ai-rules
# /plugin install frontend-plugin@ai-rules
# /plugin install devops-plugin@ai-rules

# 4. Activate and authenticate
/reload-plugins
/mcp
```

Equivalent CLI:

```sh
claude plugin marketplace add alonw0/web-asset-generator
claude plugin marketplace add anthropics/skills
claude plugin marketplace add thedotmack/claude-mem
claude plugin marketplace add nicobailon/visual-explainer
claude plugin marketplace add max-sixty/jean-claude
claude plugin marketplace add bernatmv/ai-rules
claude plugin install fullstack-plugin@ai-rules
claude plugin install spec-workflow-plugin@ai-rules   # optional
```

Install only what you need:

| Need                                                    | Install                         |
| ------------------------------------------------------- | ------------------------------- |
| Full stack (core + frontend + devops)                   | `fullstack-plugin@ai-rules`     |
| PR workflows, GitHub, Notion, documents, Google         | `core-plugin@ai-rules`          |
| UI design, Figma, browser testing, DevTools, web assets | `frontend-plugin@ai-rules`      |
| Supabase, Vercel                                        | `devops-plugin@ai-rules`        |
| Spec-Driven Development                                 | `spec-workflow-plugin@ai-rules` |

### Project / local install

Use this when plugins should be tied to **this repository** — for team defaults or when developing the marketplace itself.

| Scope       | Who gets it                                        | When to use                                       |
| ----------- | -------------------------------------------------- | ------------------------------------------------- |
| **Project** | Everyone who clones the repo and trusts the folder | Team-shared plugin set in `.claude/settings.json` |
| **Local**   | Only you, only in this repo checkout               | Personal overrides while working in ai-rules      |

If you clone this repo and trust the project folder, [`.claude/settings.json`](.claude/settings.json) registers third-party marketplaces via `extraKnownMarketplaces` — skip the third-party marketplace steps from the global install section above.

```sh
/plugin marketplace add bernatmv/ai-rules
/plugin install fullstack-plugin@ai-rules --scope project
/plugin install spec-workflow-plugin@ai-rules --scope project   # optional
/reload-plugins
/mcp
```

Use `--scope local` instead of `--scope project` for a personal-only install in this checkout.

### Post-install validation

```sh
claude --version
claude plugin list
```

In Claude Code:

1. `/plugin` → **Installed** — confirm enabled plugins:
   - `fullstack-plugin@ai-rules` (or individual core/frontend/devops plugins)
   - `spec-workflow-plugin@ai-rules` (if installed)
2. Confirm key dependencies, for example:
   - `superpowers@claude-plugins-official` (core)
   - `figma@claude-plugins-official` (frontend)
   - `vercel@claude-plugins-official` (devops)
3. `/plugin` → **Errors** — should be empty. If you see `dependency-unsatisfied`, add the missing marketplace and reinstall.
4. `/reload-plugins` — check skill and MCP server counts.
5. `/mcp` — authenticate MCP services you use (Figma, GitHub, Vercel, Supabase, etc.).
6. Google Workspace — ask Claude to `Set up Google authentication for jean-claude` (requires [uv](https://docs.astral.sh/uv/)).

Optional JSON check:

```sh
claude plugin list --json | jq '.[] | select(.marketplace=="ai-rules") | {name, enabled, errors}'
```

Spot-check skills:

- Core: `/core-plugin:babysit-pr` or `/core-plugin:launch-playbook`
- Ralph PRD converter: `/core-plugin:ralph`
- TDD: `/superpowers:test-driven-development`
- Superpowers: `/superpowers:brainstorming`
- Figma: open a Figma URL or ask Claude to use Figma MCP (after `/mcp` auth)
- SDD: `/spec-workflow-plugin:sdd-create-prd` (after workspace setup)

### Uninstall / cleanup

```sh
claude plugin uninstall fullstack-plugin@ai-rules --prune
claude plugin uninstall spec-workflow-plugin@ai-rules --prune
claude plugin prune --dry-run
```

To uninstall individual plugins instead of the bundle:

```sh
claude plugin uninstall core-plugin@ai-rules --prune
claude plugin uninstall frontend-plugin@ai-rules --prune
claude plugin uninstall devops-plugin@ai-rules --prune
```

## Creating a New Plugin

```bash
./scripts/init-plugin.sh <plugin-name>
```

## Creating a New Skill

```bash
./scripts/create-skill.sh <plugin-name> <skill-name>
```
