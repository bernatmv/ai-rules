# ai-rules

Personal configuration for AI-assisted coding: shared instructions for agents, Cursor skills, and Claude Code setup in one place.

## What lives here

| Path | Role |
|------|------|
| [`AGENTS.md`](AGENTS.md) | Agent instructions (code review checklist and quality bar). Cursor and compatible tools load this from the repo root. |
| [`CLAUDE.md`](CLAUDE.md) | Intended to mirror `AGENTS.md` (e.g. symlink) so Claude Code picks up the same rules. |
| [`.cursor/skills/`](.cursor/skills/) | Cursor skills: `frontend-design`, `launch-playbook`, `pdf`, `prd`, `ralph`, `skill-creator`, `test-driven-development`. |
| [`.cursor/SKILLS.md`](.cursor/SKILLS.md) | Notes on where skills live and parity with Claude Code plugins. |
| [`.cursor/MCP.md`](.cursor/MCP.md) | MCP-related notes for Cursor. |
| [`.claude/`](.claude/) | Claude Code hooks, settings, and plugin notes. |
| [`docs/`](docs/) | Reference material (e.g. Claude layout diagrams); listed in [`.cursorignore`](.cursorignore) so it is not indexed as project context by default. |
| [`agents/`](agents/), [`rules/`](rules/) | Reserved for future agent definitions or rule packs (currently empty). |

## Using this repo

1. **Clone or copy** the tree where you want your global or project rules to live.
2. **Point your editor** at this folder, or copy only the pieces you need (for example `.cursor/skills` into `~/.cursor/skills/` per `.cursor/SKILLS.md`).
3. **Align Claude with agents**: keep `CLAUDE.md` in sync with `AGENTS.md`—a symlink from `CLAUDE.md` to `AGENTS.md` avoids drift if both tools should follow the same text.

There is no install script or package manager step; treat this as a dotfiles-style ruleset you version and sync yourself.

## License

No license file is present in the root of this repository. Add one if you intend to share or publish the contents.
