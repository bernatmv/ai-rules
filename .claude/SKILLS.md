# Skills from `.claude/SKILLS.md`

These skills install automatically via `ai-rules` plugin dependencies — no manual `npx skills add` required.

## Install

```sh
/plugin marketplace add coreyhaines31/marketingskills   # marketing-plugin (marketing skills)
/plugin marketplace add vercel-labs/agent-browser       # frontend-plugin (browser automation CLI)
/plugin marketplace add heygen-com/hyperframes            # frontend-plugin (HyperFrames video + animation skills)
/plugin marketplace add bernatmv/ai-rules
/plugin install fullstack-plugin@ai-rules    # or core-plugin / frontend-plugin individually
/reload-plugins
```

## Skill → plugin mapping

| Skill                   | Installed via                                      | Slash command                    |
| ----------------------- | -------------------------------------------------- | -------------------------------- |
| `agent-browser`         | `frontend-plugin` → `agent-browser`                | `/agent-browser:agent-browser`    |
| `ui-character-and-polish` | `frontend-plugin` (bundled)                     | `/frontend-plugin:ui-character-and-polish` |
| `remotion-best-practices` (router) | `frontend-plugin` → `remotion-plugin`   | `/remotion-plugin:remotion-best-practices` |
| `remotion-create`, `remotion-render`, `remotion-captions`, … | `frontend-plugin` → `remotion-plugin` | `/remotion-plugin:<skill-name>` |
| `hyperframes`           | `frontend-plugin` → `hyperframes`                  | `/hyperframes:hyperframes`       |
| `remotion-to-hyperframes` | `frontend-plugin` → `hyperframes`                | `/hyperframes:remotion-to-hyperframes` |
| `gsap`, `lottie`, …     | `frontend-plugin` → `hyperframes`                  | `/hyperframes:<skill-name>`    |
| `create-roblox-game`, `roblox-*`, `studify`, `blender-*`, … | `roblox-gamedev` | `/roblox-gamedev:<skill-name>` |
| `excalidraw-diagram`    | `core-plugin` → `excalidraw-plugin`                | `/excalidraw-plugin:excalidraw-diagram` |
| `skill-creator`         | `core-plugin` → `skill-creator`                    | `/skill-creator:skill-creator`          |
| `shadcn`                | `devops-plugin` → `vercel`                         | `/vercel:shadcn`                 |
| `next-best-practices`   | `devops-plugin` → `vercel` (`nextjs` skill)        | `/vercel:nextjs`                 |
| Vercel agent skills     | `devops-plugin` → `vercel`                         | `/vercel:*`                      |
| `app-store-screenshots` | `frontend-plugin` → `app-store-screenshots-plugin` | `/app-store-screenshots-plugin:app-store-screenshots` |
| `seo-audit`             | `marketing-plugin` → `marketing-skills`            | `/marketing-skills:seo-audit`    |
| `copywriting`           | `marketing-plugin` → `marketing-skills`            | `/marketing-skills:copywriting`  |
| `first-100-customers`   | `marketing-plugin`                                 | `/marketing-plugin:first-100-customers` |
| `seo-keyword-research` | `marketing-plugin`                                 | `/marketing-plugin:seo-keyword-research` |
| `seo-strategy`         | `marketing-plugin`                                 | `/marketing-plugin:seo-strategy`         |
| `ai-video-storyboard`   | `ai-video`                                         | `/ai-video:ai-video-storyboard`   |
| `ai-video-prompt-enhancer` | `ai-video`                                      | `/ai-video:ai-video-prompt-enhancer` |
| `tiktok-reel-hook-generator` | `ai-video`                                    | `/ai-video:tiktok-reel-hook-generator` |
| `video-prompting`       | `ai-video`                                         | `/ai-video:video-prompting`       |
| `visual-image`          | `ai-video`                                         | `/ai-video:visual-image`          |
| `character-design-sheet` | `ai-video`                                        | `/ai-video:character-design-sheet` |

`marketing-skills` ([marketingskills](https://github.com/coreyhaines31/marketingskills)) ships 41 skills; `marketing-plugin` depends on the whole plugin. Highlighted above: `seo-audit` and `copywriting`.

`hyperframes` ([heygen-com/hyperframes](https://github.com/heygen-com/hyperframes)) ships 15 skills — HTML-to-video, GSAP/Lottie/Three.js/WAAI animations, website capture, and Remotion migration. Highlighted above: `hyperframes`, `remotion-to-hyperframes`. Full catalog: [claudemarketplaces](https://claudemarketplaces.com/skills/heygen-com/hyperframes).

`roblox-gamedev` bundles 44 skills and 7 worker agents; see [`roblox-gamedev/README.md`](../roblox-gamedev/README.md).

**Overlap check:** `agent-browser` is the default CLI for browser automation (snapshot + `@eN` refs, low token cost). `playwright` MCP complements it for MCP-native tool-calling flows. `chrome-devtools-mcp` covers debugging and performance — not duplicated.

**Overlap check:** `copywriting` and `seo-audit` complement `frontend-design` (UI implementation), core `prd` (requirements), and the launch playbook bundled in `first-100-customers` (launch ops) — they do not duplicate them.

**Overlap check:** `first-100-customers` (`marketing-plugin`) is the GTM *orchestrator* — a 7-channel weekly acquisition engine. It bundles the 56-platform launch playbook (platform-by-platform launch ops, `references/launch-playbook/`) and hands off to `marketing-skills:*` (`launch`, `cold-email`, `prospecting`, `social`, `community-marketing`, `onboarding`, `referrals`, …) for per-channel depth — sequencing layer over them, not a duplicate.

**Overlap check:** [`shadcn`](https://claudemarketplaces.com/skills/shadcn/ui/shadcn) (component management via `/vercel:shadcn`) complements `frontend-design` (creative UI design) — not duplicated.

**Overlap check:** `remotion-plugin` (React programmatic video) and `hyperframes` (HTML/GSAP video) complement each other — use `/hyperframes:remotion-to-hyperframes` to bridge Remotion projects into HyperFrames. Animation adapter skills (`gsap`, `lottie`, `three`, `animejs`, `css-animations`, `waapi`, `tailwind`) are HyperFrames-specific, not duplicated by `remotion-plugin`.


## Upstream sources

| Skill                           | Source                                                                                               |
| ------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `agent-browser`                 | [vercel-labs/agent-browser](https://github.com/vercel-labs/agent-browser) via `agent-browser@agent-browser` |
| `remotion-*` (13 skills)        | [remotion-dev/skills](https://github.com/remotion-dev/skills) via `remotion-plugin@ai-rules`         |
| `hyperframes`, `gsap`, `lottie`, … | [heygen-com/hyperframes](https://github.com/heygen-com/hyperframes) via `hyperframes@hyperframes` ([claudemarketplaces](https://claudemarketplaces.com/skills/heygen-com/hyperframes)) |
| `roblox-gamedev` skills        | [SyphoDev-yt/roblox-ai-skills](https://github.com/SyphoDev-yt/roblox-ai-skills) ([SyphoDev YouTube](https://www.youtube.com/@SyphoDev)), [mvvthw/roblox-claude-skills](https://github.com/mvvthw/roblox-claude-skills), [zriptic/roclicks-skills](https://github.com/zriptic/roclicks-skills), [RobLe3/cc-blender-skill](https://github.com/RobLe3/cc-blender-skill) via `roblox-gamedev@ai-rules` |
| `excalidraw-diagram`            | [coleam00/excalidraw-diagram-skill](https://github.com/coleam00/excalidraw-diagram-skill)            |
| `skill-creator`                 | [anthropics/skills](https://github.com/anthropics/skills) via `skill-creator@claude-plugins-official` ([claudemarketplaces](https://claudemarketplaces.com/skills/anthropics/skills/skill-creator)) |
| `shadcn`                        | [shadcn-ui/ui](https://github.com/shadcn-ui/ui) via `vercel@claude-plugins-official` ([claudemarketplaces](https://claudemarketplaces.com/skills/shadcn/ui/shadcn)) |
| Next.js, Vercel agent stack     | [vercel/vercel-plugin](https://github.com/vercel/vercel-plugin) via `vercel@claude-plugins-official` |
| `app-store-screenshots`         | [ParthJadhav/app-store-screenshots](https://github.com/ParthJadhav/app-store-screenshots)            |
| `seo-audit`, `copywriting`, …   | [coreyhaines31/marketingskills](https://github.com/coreyhaines31/marketingskills) via `marketing-skills@marketingskills` |
| `first-100-customers`           | Authored in-repo via `marketing-plugin@ai-rules`; playbook adapted from [@fin465's thread](https://x.com/fin465/status/2066589201085370482) |
| `ai-video-storyboard`, `ai-video-prompt-enhancer`, `tiktok-reel-hook-generator` | [aicontentskills/ai-video-storyboard-skill](https://github.com/aicontentskills/ai-video-storyboard-skill), [ai-video-prompt-enhancer](https://github.com/aicontentskills/ai-video-prompt-enhancer), [tiktok-reel-hook-generator](https://github.com/aicontentskills/tiktok-reel-hook-generator) via `ai-video@ai-rules` (no upstream LICENSE) |
| `video-prompting`               | [Square-Zero-Labs/video-prompting-skill](https://github.com/Square-Zero-Labs/video-prompting-skill) via `ai-video@ai-rules` (Apache-2.0) |
| `visual-image`                  | [smixs/visual-skills](https://github.com/smixs/visual-skills) via `ai-video@ai-rules` (MIT; upstream `image`) |
| `character-design-sheet`        | [inference-sh/skills](https://github.com/inference-sh/skills) via `ai-video@ai-rules` (MIT) |

## Manual install (without ai-rules plugins)

```sh
npx skills add vercel-labs/agent-browser
npx skills add remotion/agent-skills
npx skills add https://github.com/heygen-com/hyperframes
npx skills add https://github.com/coleam00/excalidraw-diagram-skill --skill excalidraw-diagram
npx skills add https://github.com/anthropics/skills --skill skill-creator
npx skills add https://github.com/shadcn/ui --skill shadcn
npx skills add vercel-labs/agent-skills
npx skills add https://github.com/vercel-labs/next-skills --skill next-best-practices
npx skills add ParthJadhav/app-store-screenshots
npx skills add https://github.com/coreyhaines31/marketingskills --skill seo-audit
npx skills add https://github.com/coreyhaines31/marketingskills --skill copywriting
npx skills add https://github.com/aicontentskills/ai-video-storyboard-skill
npx skills add https://github.com/aicontentskills/ai-video-prompt-enhancer
npx skills add https://github.com/aicontentskills/tiktok-reel-hook-generator
npx skills add https://github.com/Square-Zero-Labs/video-prompting-skill --skill video-prompting
npx skills add https://github.com/smixs/visual-skills --skill image
npx skills add inferen-sh/skills --skill character-design-sheet --agent claude-code
```

Skills are loaded from `~/.claude/skills/` when installed manually.
