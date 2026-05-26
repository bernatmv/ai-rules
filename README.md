# ai-rules

A curated marketplace of Claude Code plugins with skills for various tools and workflows.

Personal configuration for AI-assisted coding: shared instructions for agents, Cursor skills, and Claude Code setup in one place.

## Plugins

| Plugin                                         | Description                                                                                          |
| ---------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| [core-plugin](./core-plugin)                   | Core skills plus bundled plugin dependencies (MCP integrations, Github, JIRA, and third-party tools) |
| [devops-plugin](./devops-plugin)               | CI/CD, Kubernetes                                                                                    |
| [frontend-plugin](./frontend-plugin)           | Base code skills for a Frontend TS/JS stack                                                          |
| [spec-workflow-plugin](./spec-workflow-plugin) | Spec-Driven Development (SDD) — spec creation, review, implementation, and workflow management       |

See [Installation](#installation) below (global install recommended for most devs), [`.claude/PLUGIN.md`](.claude/PLUGIN.md) for dependency details, and [`.claude/MCP.md`](.claude/MCP.md) for MCP setup.

## core-plugin contents

### Bundled skills

Skills shipped directly in `core-plugin/skills/`:

| Skill                     | Purpose                                                           |
| ------------------------- | ----------------------------------------------------------------- |
| `babysit-pr`              | Keep a PR merge-ready: triage comments, resolve conflicts, fix CI |
| `plugin-advisor`          | Recommend Claude Code plugins for a codebase                      |
| `prd`                     | Generate product requirements documents                           |
| `test-driven-development` | TDD workflow and anti-patterns                                    |

PDF and skill authoring come from dependency plugins (`document-skills`, `skill-creator`) instead of bundled copies.

### Auto-installed plugin dependencies

Installing `core-plugin@ai-rules` also installs these plugins via
`core-plugin/.claude-plugin/plugin.json`.

#### Official (`claude-plugins-official`)

| Plugin                | Purpose                                                       |
| --------------------- | ------------------------------------------------------------- |
| `frontend-design`     | Frontend UI design guidance                                   |
| `superpowers`         | Development workflows (TDD, planning, debugging, code review) |
| `code-review`         | PR and code review agents                                     |
| `code-simplifier`     | Code simplification workflows                                 |
| `github`              | GitHub MCP integration                                        |
| `playwright`          | Playwright MCP for browser automation                         |
| `ralph-loop`          | Autonomous iteration loop (`/ralph-loop`)                     |
| `figma`               | Figma MCP integration                                         |
| `supabase`            | Supabase MCP integration                                      |
| `atlassian`           | Jira and Confluence MCP integration                           |
| `vercel`              | Vercel MCP integration                                        |
| `gitlab`              | GitLab MCP integration                                        |
| `chrome-devtools-mcp` | Chrome DevTools MCP                                           |
| `stripe`              | Stripe MCP integration                                        |
| `huggingface-skills`  | Hugging Face Hub skills and MCP                               |
| `skill-creator`       | Create, evaluate, and improve agent skills                    |
| `notion`              | Notion MCP integration                                        |

#### Third-party

| Plugin                | Marketplace                       | Purpose                                   |
| --------------------- | --------------------------------- | ----------------------------------------- |
| `web-asset-generator` | `web-asset-generator-marketplace` | Favicons, app icons, Open Graph images    |
| `document-skills`     | `anthropic-agent-skills`          | Excel, Word, PowerPoint, PDF processing   |
| `claude-mem`          | `thedotmack`                      | Persistent memory across sessions         |
| `visual-explainer`    | `visual-explainer-marketplace`    | HTML diagrams, diff reviews, plan reviews |

### MCP servers in core-plugin

Service MCPs (Notion, Stripe, GitHub, etc.) come from the plugin dependencies above.
`core-plugin/.mcp.json` only adds MCPs without a matching plugin:

| Server       | Purpose                    |
| ------------ | -------------------------- |
| `convex`     | Convex backend MCP         |
| `astro-docs` | Astro documentation search |

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

Requires **Claude Code v2.1.110+** (plugin dependencies). **v2.1.143+** recommended so dependency plugins enable automatically with `core-plugin`.

Installing `core-plugin@ai-rules` pulls in all bundled skills and the 21 dependency plugins listed above.

### Global install (recommended)

Use this when you want plugins available in **every project** on your machine. This is the default install scope (user scope).

Run once from any directory — inside or outside this repo:

```sh
# 1. Third-party marketplaces (one-time; required for dependency resolution)
/plugin marketplace add alonw0/web-asset-generator
/plugin marketplace add anthropics/skills
/plugin marketplace add thedotmack/claude-mem
/plugin marketplace add nicobailon/visual-explainer

# 2. ai-rules marketplace and core-plugin (installs all dependencies)
/plugin marketplace add bernatmv/ai-rules
/plugin install core-plugin@ai-rules

# 3. Activate and authenticate
/reload-plugins
/mcp
```

Equivalent CLI (same user/global scope):

```sh
claude plugin marketplace add alonw0/web-asset-generator
claude plugin marketplace add anthropics/skills
claude plugin marketplace add thedotmack/claude-mem
claude plugin marketplace add nicobailon/visual-explainer
claude plugin marketplace add bernatmv/ai-rules
claude plugin install core-plugin@ai-rules
```

Official plugins (`superpowers`, `github`, `figma`, etc.) resolve automatically — `claude-plugins-official` is built into Claude Code.

Install other marketplace plugins globally the same way:

```sh
/plugin install devops-plugin@ai-rules
/plugin install frontend-plugin@ai-rules
/plugin install spec-workflow-plugin@ai-rules
/reload-plugins
```

### Project / local install

Use this when plugins should be tied to **this repository** — for team defaults or when developing the marketplace itself.

| Scope       | Who gets it                                        | When to use                                                 |
| ----------- | -------------------------------------------------- | ----------------------------------------------------------- |
| **Project** | Everyone who clones the repo and trusts the folder | Team-shared plugin set checked into `.claude/settings.json` |
| **Local**   | Only you, only in this repo checkout               | Personal overrides while working in ai-rules                |

If you clone this repo and trust the project folder, [`.claude/settings.json`](.claude/settings.json) already registers third-party marketplaces via `extraKnownMarketplaces` — you can skip the third-party marketplace steps from the global install section above.

```sh
# From the ai-rules repo root (or any trusted project checkout)
/plugin marketplace add bernatmv/ai-rules

# Project scope — shared with teammates via .claude/settings.json
/plugin install core-plugin@ai-rules --scope project

# OR local scope — only you, only in this checkout
/plugin install core-plugin@ai-rules --scope local

/reload-plugins
/mcp
```

CLI equivalent:

```sh
claude plugin install core-plugin@ai-rules --scope project
# or
claude plugin install core-plugin@ai-rules --scope local
```

### Post-install validation

After install, confirm everything loaded correctly:

```sh
# Version check
claude --version

# List installed plugins and dependency errors
claude plugin list
```

In Claude Code:

1. Run `/plugin` → **Installed** — confirm `core-plugin@ai-rules` is enabled.
2. Confirm key dependencies are present and enabled, for example:
   - `superpowers@claude-plugins-official`
   - `document-skills@anthropic-agent-skills`
   - `skill-creator@claude-plugins-official`
   - `github@claude-plugins-official`
3. Run `/plugin` → **Errors** — should be empty. If you see `dependency-unsatisfied`, add the missing marketplace from the global install steps above and run `/plugin install core-plugin@ai-rules` again.
4. Run `/reload-plugins` — note the skill and MCP server counts in the output.
5. Run `/mcp` — authenticate the services you use (GitHub, Notion, Figma, etc.). Skills work without this step; MCP tools do not.

Optional JSON check:

```sh
claude plugin list --json | jq '.[] | select(.name=="core-plugin") | {name, enabled, errors}'
```

Spot-check that skills are recognized:

- Core: `/core-plugin:babysit-pr` (or ask Claude to babysit a PR — skill triggers from description)
- Superpowers: `/superpowers:brainstorming` (or similar superpowers skill)
- Document skills: `/document-skills:pdf`

### Uninstall / cleanup

```sh
# Remove core-plugin and orphaned auto-installed dependencies
claude plugin uninstall core-plugin@ai-rules --prune

# Preview orphans without removing
claude plugin prune --dry-run
```

### Cursor skills (separate from Claude Code plugins)

Cursor skills in [`.cursor/skills/`](.cursor/skills/) are installed independently:

```sh
npx skills add bernatmv/ai-rules -a cursor -g -y
npx skills add bernatmv/ai-rules --list
npx skills add bernatmv/ai-rules --skill frontend-design -a cursor -g -y
```

### Rules in one place

Put (or keep) instructions in [`CLAUDE.md`](CLAUDE.md) and link to it for Cursor or other agents. On Unix you can replace `AGENTS.md` with a symlink to `CLAUDE.md` if you prefer identical bytes on disk.

## Creating a New Plugin

```bash
./scripts/init-plugin.sh <plugin-name>
```

## Creating a New Skill

```bash
./scripts/create-skill.sh <plugin-name> <skill-name>
```
