# ai-rules

A curated marketplace of Claude Code plugins with skills for various tools and workflows.

**Guide:** [MARKETPLACE-GUIDE.md](MARKETPLACE-GUIDE.md) — how to use and contribute to the marketplace

Personal configuration for AI-assisted coding: shared instructions for agents, Cursor skills, and Claude Code setup in one place.

## Plugins

| Plugin                                               | Description                                                                                    |
| ---------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| [core-plugin](./core-plugin)                         | Core skills and MCP integrations (Jira, Confluence, PR Reviews and anything code-adjacent)     |
| [devops-plugin](./devops-plugin)                     | CI/CD, Kubernetes                                                                              |
| [obra-superpowers-plugin](./obra-superpowers-plugin) | Development workflows (TDD, code review, debugging, planning)                                  |
| [frontend-plugin](./frontend-plugin)                 | Base code skills for a Frontend TS/JS stack                                                    |
| [spec-workflow-plugin](./spec-workflow-plugin)       | Spec-Driven Development (SDD) — spec creation, review, implementation, and workflow management |

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

## Using this repo

1. **Point your editor** at this folder, or copy only the pieces you need (for example `.claude/skills` into `~/.claude/skills/` per `.claude/SKILLS.md`). Or use install commands:

```
# Skills (works now)
npx skills add bernatmv/ai-rules -a cursor -g -y
npx skills add bernatmv/ai-rules -a claude-code -g -y

# Claude Code marketplace
/plugin marketplace add bernatmv/ai-rules
/plugin install core-plugin@ai-rules

# List what's available
npx skills add bernatmv/ai-rules --list

# Install all skills to Cursor globally
npx skills add bernatmv/ai-rules -a cursor -g -y

# Install all skills to Claude Code globally
npx skills add bernatmv/ai-rules -a claude-code -g -y

# Install one skill
npx skills add bernatmv/ai-rules --skill frontend-design -a cursor -g -y
```

2. **Rules in one place**: put (or keep) instructions in `CLAUDE.md` links to it for Cursor or other agents; on Unix you can replace `AGENTS.md` with a symlink to `CLAUDE.md` if you prefer identical bytes on disk.

## Creating a New Plugin

```bash
./scripts/init-plugin.sh <plugin-name>
```

## Creating a New Skill

```bash
./scripts/create-skill.sh <plugin-name> <skill-name>
```
