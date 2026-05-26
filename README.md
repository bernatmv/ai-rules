# ai-rules

A curated marketplace of Claude Code plugins with skills for various tools and workflows.

Personal configuration for AI-assisted coding: shared instructions for agents, Cursor skills, and Claude Code setup in one place.

## Plugins

| Plugin                                         | Description                                                                                     |
| ---------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| [core-plugin](./core-plugin)                   | Core skills plus engineering workflows, GitHub/Jira/Notion, documents, and productivity plugins |
| [frontend-plugin](./frontend-plugin)           | Frontend design, Figma, Playwright, Chrome DevTools, web assets, and Astro docs MCP             |
| [devops-plugin](./devops-plugin)               | Supabase and Vercel MCP integrations                                                            |
| [spec-workflow-plugin](./spec-workflow-plugin) | Spec-Driven Development (SDD) — spec creation, review, implementation, and workflow management  |

See [Installation](#installation) below (global install recommended for most devs), [`.claude/PLUGIN.md`](.claude/PLUGIN.md) for dependency details, and [`.claude/MCP.md`](.claude/MCP.md) for MCP setup.

## Plugin contents

### core-plugin

#### Bundled skills

| Skill                     | Purpose                                                           |
| ------------------------- | ----------------------------------------------------------------- |
| `babysit-pr`              | Keep a PR merge-ready: triage comments, resolve conflicts, fix CI |
| `plugin-advisor`          | Recommend Claude Code plugins for a codebase                      |
| `prd`                     | Generate product requirements documents                           |
| `test-driven-development` | TDD workflow and anti-patterns                                    |

PDF and skill authoring come from dependency plugins (`document-skills`, `skill-creator`).

#### Dependencies (15)

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

#### MCP in core-plugin

| Server   | Purpose            |
| -------- | ------------------ |
| `convex` | Convex backend MCP |

### frontend-plugin

#### Dependencies (5)

| Plugin                | Purpose                                |
| --------------------- | -------------------------------------- |
| `frontend-design`     | Frontend UI design guidance            |
| `playwright`          | Playwright MCP for browser automation  |
| `figma`               | Figma MCP and design workflow skills   |
| `chrome-devtools-mcp` | Chrome DevTools MCP                    |
| `web-asset-generator` | Favicons, app icons, Open Graph images |

#### MCP in frontend-plugin

| Server       | Purpose                    |
| ------------ | -------------------------- |
| `astro-docs` | Astro documentation search |

### devops-plugin

#### Dependencies (2)

| Plugin     | Purpose                  |
| ---------- | ------------------------ |
| `supabase` | Supabase MCP integration |
| `vercel`   | Vercel MCP integration   |

## What lives here

| Path                                     | Role                                                                                                                                             |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| [`AGENTS.md`](AGENTS.md)                 | Duplicate of CLAUDE.md, use only if not using Claude Code one.                                                                                   |
| [`CURSOR.md`](CURSOR.md)                 | Short pointer to [`AGENTS.md`](AGENTS.md) for Cursor when it uses this root-level file.                                                          |
| [`CLAUDE.md`](CLAUDE.md)                 | Claude instructions based on Andrej Karpathy's rules                                                                                             |
| [`.cursor/skills/`](.cursor/skills/)     | Cursor skills: `frontend-design`, `launch-playbook`, `pdf`, `prd`, `ralph`, `skill-creator`, `test-driven-development`.                          |
| [`.cursor/SKILLS.md`](.cursor/SKILLS.md) | Notes on where skills live and parity with Claude Code plugins.                                                                                  |
| [`.cursor/MCP.md`](.cursor/MCP.md)       | MCP-related notes for Cursor.                                                                                                                    |
| [`.claude/`](.claude/)                   | Claude Code hooks, settings, and plugin notes.                                                                                                   |
| [`docs/`](docs/)                         | Reference material (e.g. Claude layout diagrams); listed in [`.cursorignore`](.cursorignore) so it is not indexed as project context by default. |
| [`agents/`](agents/), [`rules/`](rules/) | Reserved for future agent definitions or rule packs (currently empty).                                                                           |

## Installation

Requires **Claude Code v2.1.110+** (plugin dependencies). **v2.1.143+** recommended so dependency plugins enable automatically.

**Prerequisite for Google Workspace:** install [uv](https://docs.astral.sh/uv/) before using the `jean-claude` dependency (via `core-plugin`).

### Global install (recommended)

Use this when you want plugins available in **every project** on your machine (user scope).

Run once from any directory:

```sh
# 1. Third-party marketplaces (one-time; add only what your plugins need)
/plugin marketplace add alonw0/web-asset-generator   # frontend-plugin
/plugin marketplace add anthropics/skills            # core-plugin
/plugin marketplace add thedotmack/claude-mem        # core-plugin
/plugin marketplace add nicobailon/visual-explainer  # core-plugin
/plugin marketplace add max-sixty/jean-claude        # core-plugin

# 2. ai-rules marketplace
/plugin marketplace add bernatmv/ai-rules

# 3. Install plugins (pick all three for the full stack, or install individually)
/plugin install core-plugin@ai-rules
/plugin install frontend-plugin@ai-rules
/plugin install devops-plugin@ai-rules

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
claude plugin install core-plugin@ai-rules
claude plugin install frontend-plugin@ai-rules
claude plugin install devops-plugin@ai-rules
```

Official plugins (`superpowers`, `figma`, `vercel`, etc.) resolve automatically — `claude-plugins-official` is built into Claude Code.

Install only what you need:

| Need                                                    | Install                    |
| ------------------------------------------------------- | -------------------------- |
| PR workflows, GitHub, Notion, documents, Google         | `core-plugin@ai-rules`     |
| UI design, Figma, browser testing, DevTools, web assets | `frontend-plugin@ai-rules` |
| Supabase, Vercel                                        | `devops-plugin@ai-rules`   |
| Full stack                                              | all three                  |

Optional:

```sh
/plugin install spec-workflow-plugin@ai-rules
/reload-plugins
```

### Project / local install

Use this when plugins should be tied to **this repository** — for team defaults or when developing the marketplace itself.

| Scope       | Who gets it                                        | When to use                                       |
| ----------- | -------------------------------------------------- | ------------------------------------------------- |
| **Project** | Everyone who clones the repo and trusts the folder | Team-shared plugin set in `.claude/settings.json` |
| **Local**   | Only you, only in this repo checkout               | Personal overrides while working in ai-rules      |

If you clone this repo and trust the project folder, [`.claude/settings.json`](.claude/settings.json) registers third-party marketplaces via `extraKnownMarketplaces` — skip the third-party marketplace steps from the global install section above.

```sh
/plugin marketplace add bernatmv/ai-rules
/plugin install core-plugin@ai-rules --scope project
/plugin install frontend-plugin@ai-rules --scope project
/plugin install devops-plugin@ai-rules --scope project
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
   - `core-plugin@ai-rules`
   - `frontend-plugin@ai-rules` (if installed)
   - `devops-plugin@ai-rules` (if installed)
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

- Core: `/core-plugin:babysit-pr`
- Superpowers: `/superpowers:brainstorming`
- Figma: open a Figma URL or ask Claude to use Figma MCP (after `/mcp` auth)

### Uninstall / cleanup

```sh
claude plugin uninstall core-plugin@ai-rules --prune
claude plugin uninstall frontend-plugin@ai-rules --prune
claude plugin uninstall devops-plugin@ai-rules --prune
claude plugin prune --dry-run
```

### Cursor skills (separate from Claude Code plugins)

```sh
npx skills add bernatmv/ai-rules -a cursor -g -y
npx skills add bernatmv/ai-rules --list
npx skills add bernatmv/ai-rules --skill frontend-design -a cursor -g -y
```

### Rules in one place

Put (or keep) instructions in [`CLAUDE.md`](CLAUDE.md) and link to it for Cursor or other agents. On Unix you can replace `AGENTS.md` with a symlink to `CLAUDE.md`.

## Creating a New Plugin

```bash
./scripts/init-plugin.sh <plugin-name>
```

## Creating a New Skill

```bash
./scripts/create-skill.sh <plugin-name> <skill-name>
```
