# Skills from `.claude/SKILLS.md`

These skills install automatically via `ai-rules` plugin dependencies — no manual `npx skills add` required.

## Install

```sh
/plugin marketplace add bernatmv/ai-rules
/plugin install fullstack-plugin@ai-rules    # or core-plugin / frontend-plugin individually
/reload-plugins
```

## Skill → plugin mapping

| Skill                   | Installed via                                      | Slash command                                         |
| ----------------------- | -------------------------------------------------- | ----------------------------------------------------- |
| `browser-use`           | `frontend-plugin` → `browser-use-plugin`           | `/browser-use-plugin:browser-use`                     |
| `remotion`              | `frontend-plugin` → `remotion-plugin`              | `/remotion-plugin:remotion`                           |
| `excalidraw-diagram`    | `core-plugin` → `excalidraw-plugin`                | `/excalidraw-plugin:excalidraw-diagram`               |
| `shadcn`                | `frontend-plugin` → `vercel`                       | `/vercel:shadcn`                                      |
| `next-best-practices`   | `frontend-plugin` → `vercel` (`nextjs` skill)      | `/vercel:nextjs`                                      |
| Vercel agent skills     | `devops-plugin` → `vercel`                         | `/vercel:*` (e.g. `/vercel:deployments-cicd`)         |
| `app-store-screenshots` | `frontend-plugin` → `app-store-screenshots-plugin` | `/app-store-screenshots-plugin:app-store-screenshots` |

## Upstream sources

| Skill                           | Source                                                                                               |
| ------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `browser-use`                   | [browser-use/browser-use](https://github.com/browser-use/browser-use)                                |
| `remotion`                      | [remotion-dev/skills](https://github.com/remotion-dev/skills)                                        |
| `excalidraw-diagram`            | [coleam00/excalidraw-diagram-skill](https://github.com/coleam00/excalidraw-diagram-skill)            |
| `shadcn`, Next.js, Vercel stack | [vercel/vercel-plugin](https://github.com/vercel/vercel-plugin) via `vercel@claude-plugins-official` |
| `app-store-screenshots`         | [ParthJadhav/app-store-screenshots](https://github.com/ParthJadhav/app-store-screenshots)            |

## Manual install (without ai-rules plugins)

Only needed if you are not using the marketplace plugins above:

```sh
npx skills add https://github.com/browser-use/browser-use --skill browser-use
npx skills add remotion/agent-skills
npx skills add https://github.com/coleam00/excalidraw-diagram-skill --skill excalidraw-diagram
npx skills add shadcn/ui
npx skills add vercel-labs/agent-skills
npx skills add https://github.com/vercel-labs/next-skills --skill next-best-practices
npx skills add ParthJadhav/app-store-screenshots
```

Skills are loaded from `~/.claude/skills/` when installed manually.
