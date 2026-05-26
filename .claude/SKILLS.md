# Skills from `.claude/SKILLS.md`

These skills install automatically via `ai-rules` plugin dependencies — no manual `npx skills add` required.

## Install

```sh
/plugin marketplace add coreyhaines31/marketingskills   # frontend-plugin (marketing skills)
/plugin marketplace add vercel-labs/agent-browser       # frontend-plugin (browser automation CLI)
/plugin marketplace add bernatmv/ai-rules
/plugin install fullstack-plugin@ai-rules    # or core-plugin / frontend-plugin individually
/reload-plugins
```

## Skill → plugin mapping

| Skill                   | Installed via                                      | Slash command                    |
| ----------------------- | -------------------------------------------------- | -------------------------------- |
| `agent-browser`         | `frontend-plugin` → `agent-browser`                | `/agent-browser:agent-browser`    |
| `remotion`              | `frontend-plugin` → `remotion-plugin`              | `/remotion-plugin:remotion`      |
| `excalidraw-diagram`    | `core-plugin` → `excalidraw-plugin`                | `/excalidraw-plugin:excalidraw-diagram` |
| `find-skills`           | `core-plugin` → `find-skills-plugin`               | `/find-skills-plugin:find-skills`       |
| `skill-creator`         | `core-plugin` → `skill-creator`                    | `/skill-creator:skill-creator`          |
| `shadcn`                | `frontend-plugin` → `vercel`                       | `/vercel:shadcn`                 |
| `next-best-practices`   | `frontend-plugin` → `vercel` (`nextjs` skill)      | `/vercel:nextjs`                 |
| Vercel agent skills     | `devops-plugin` → `vercel`                         | `/vercel:*`                      |
| `app-store-screenshots` | `frontend-plugin` → `app-store-screenshots-plugin` | `/app-store-screenshots-plugin:app-store-screenshots` |
| `seo-audit`             | `frontend-plugin` → `marketing-skills`             | `/marketing-skills:seo-audit`    |
| `copywriting`           | `frontend-plugin` → `marketing-skills`             | `/marketing-skills:copywriting`  |

`marketing-skills` ([marketingskills](https://github.com/coreyhaines31/marketingskills)) ships 41 skills; `frontend-plugin` depends on the whole plugin. Highlighted above: `seo-audit` and `copywriting`.

**Overlap check:** `agent-browser` is the default CLI for browser automation (snapshot + `@eN` refs, low token cost). `playwright` MCP complements it for MCP-native tool-calling flows. `chrome-devtools-mcp` covers debugging and performance — not duplicated.

**Overlap check:** `find-skills` searches the open skills ecosystem (`skills.sh`); `plugin-advisor` recommends Claude Code marketplace plugins; `skill-creator` authors skills — complementary, not duplicated.

**Overlap check:** `copywriting` and `seo-audit` complement `frontend-design` (UI implementation), core `prd` (requirements), and core `launch-playbook` (launch ops) — they do not duplicate them.

## Upstream sources

| Skill                           | Source                                                                                               |
| ------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `agent-browser`                 | [vercel-labs/agent-browser](https://github.com/vercel-labs/agent-browser) via `agent-browser@agent-browser` |
| `remotion`                      | [remotion-dev/skills](https://github.com/remotion-dev/skills)                                        |
| `excalidraw-diagram`            | [coleam00/excalidraw-diagram-skill](https://github.com/coleam00/excalidraw-diagram-skill)            |
| `find-skills`                   | [vercel-labs/skills](https://github.com/vercel-labs/skills) via `find-skills-plugin@ai-rules`        |
| `skill-creator`                 | [anthropics/skills](https://github.com/anthropics/skills) via `skill-creator@claude-plugins-official` ([claudemarketplaces](https://claudemarketplaces.com/skills/anthropics/skills/skill-creator)) |
| `shadcn`, Next.js, Vercel stack | [vercel/vercel-plugin](https://github.com/vercel/vercel-plugin) via `vercel@claude-plugins-official` |
| `app-store-screenshots`         | [ParthJadhav/app-store-screenshots](https://github.com/ParthJadhav/app-store-screenshots)            |
| `seo-audit`, `copywriting`, …   | [coreyhaines31/marketingskills](https://github.com/coreyhaines31/marketingskills) via `marketing-skills@marketingskills` |

## Manual install (without ai-rules plugins)

```sh
npx skills add vercel-labs/agent-browser
npx skills add remotion/agent-skills
npx skills add https://github.com/coleam00/excalidraw-diagram-skill --skill excalidraw-diagram
npx skills add https://github.com/vercel-labs/skills --skill find-skills
npx skills add https://github.com/anthropics/skills --skill skill-creator
npx skills add shadcn/ui
npx skills add vercel-labs/agent-skills
npx skills add https://github.com/vercel-labs/next-skills --skill next-best-practices
npx skills add ParthJadhav/app-store-screenshots
npx skills add https://github.com/coreyhaines31/marketingskills --skill seo-audit
npx skills add https://github.com/coreyhaines31/marketingskills --skill copywriting
```

Skills are loaded from `~/.claude/skills/` when installed manually.
