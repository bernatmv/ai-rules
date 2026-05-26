# ai-rules

A curated **Claude Code** plugin marketplace: skills, bundled official and third-party plugins, and MCP integrations for everyday engineering workflows.

## Plugins

| Plugin                                 | Description                                                                                     |
| -------------------------------------- | ----------------------------------------------------------------------------------------------- |
| [fullstack-plugin](./fullstack-plugin) | **Recommended** — bundles `core-plugin`, `frontend-plugin`, and `devops-plugin`                 |
| [core-plugin](./core-plugin)           | Core skills plus engineering workflows, GitHub/Jira/Notion, documents, and productivity plugins |
| [frontend-plugin](./frontend-plugin)   | Frontend design, Figma, agent-browser, Playwright, Chrome DevTools, web assets, marketing copy & SEO, Astro docs MCP |
| [devops-plugin](./devops-plugin)       | Supabase and Vercel MCP integrations                                                            |

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

#### Dependencies (17)

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
| `find-skills-plugin` | Discover and install skills from skills.sh (ai-rules)         |

`find-skills` complements `plugin-advisor` (marketplace plugins) and `skill-creator` (authoring) — it searches the open skills ecosystem via [skills.sh](https://skills.sh/).

#### MCP in core-plugin

| Server   | Purpose            |
| -------- | ------------------ |
| `convex` | Convex backend MCP |

### frontend-plugin

#### Dependencies (10)

| Plugin                         | Purpose                                                 |
| ------------------------------ | ------------------------------------------------------- |
| `frontend-design`              | Frontend UI design guidance                             |
| `playwright`                   | Playwright MCP for browser automation                   |
| `figma`                        | Figma MCP and design workflow skills                    |
| `chrome-devtools-mcp`          | Chrome DevTools MCP                                     |
| `web-asset-generator`          | Favicons, app icons, Open Graph images                  |
| `vercel`                       | shadcn, Next.js best practices, Vercel agent skills     |
| `agent-browser`                | Browser automation CLI ([vercel-labs/agent-browser](https://github.com/vercel-labs/agent-browser)) |
| `remotion-plugin`              | Programmatic video creation (ai-rules)                  |
| `app-store-screenshots-plugin` | App Store marketing screenshots (ai-rules)              |
| `marketing-skills`             | SEO audit, copywriting, CRO, paid ads, etc. (41 skills) |

Marketing skills from [`marketingskills`](https://github.com/coreyhaines31/marketingskills) — includes [`seo-audit`](https://claudemarketplaces.com/skills/coreyhaines31/marketingskills/seo-audit) and [`copywriting`](https://claudemarketplaces.com/skills/coreyhaines31/marketingskills/copywriting). Complements (does not duplicate) `frontend-design`, core `prd`, and core `launch-playbook`.

[`agent-browser`](https://claudemarketplaces.com/skills/vercel-labs/agent-browser/agent-browser) is the default CLI for browser automation. Complements `playwright` MCP and `chrome-devtools-mcp` — replaces the former `browser-use-plugin`.

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
/plugin marketplace add coreyhaines31/marketingskills   # frontend-plugin
/plugin marketplace add vercel-labs/agent-browser     # frontend-plugin

# 2. ai-rules marketplace
/plugin marketplace add bernatmv/ai-rules

# 3. Install (pick one approach)
/plugin install fullstack-plugin@ai-rules          # full stack — recommended

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
claude plugin marketplace add coreyhaines31/marketingskills
claude plugin marketplace add vercel-labs/agent-browser
claude plugin marketplace add bernatmv/ai-rules
claude plugin install fullstack-plugin@ai-rules
```

Install only what you need:

| Need                                                    | Install                     |
| ------------------------------------------------------- | --------------------------- |
| Full stack (core + frontend + devops)                   | `fullstack-plugin@ai-rules` |
| PR workflows, GitHub, Notion, documents, Google         | `core-plugin@ai-rules`      |
| UI design, Figma, browser testing, DevTools, web assets, marketing copy & SEO | `frontend-plugin@ai-rules`  |
| Supabase, Vercel                                        | `devops-plugin@ai-rules`    |

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

### Uninstall / cleanup

```sh
claude plugin uninstall fullstack-plugin@ai-rules --prune
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
