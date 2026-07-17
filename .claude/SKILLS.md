# Skills from `.claude/SKILLS.md`

These skills install automatically via `ai-rules` plugin dependencies — no manual `npx skills add` required.

## Install

```sh
/plugin marketplace add coreyhaines31/marketingskills   # marketing-plugin (marketing skills)
/plugin marketplace add vercel-labs/agent-browser       # frontend-plugin (browser automation CLI)
/plugin marketplace add heygen-com/hyperframes            # frontend-plugin (HyperFrames video + animation skills)
/plugin marketplace add heygen-com/skills                 # ai-tools-plugin (HeyGen AI video skills)
/plugin marketplace add bernatmv/ai-rules
/plugin install fullstack-plugin@ai-rules    # or core-plugin / frontend-plugin individually
/reload-plugins
```

## Skill → plugin mapping

| Skill                   | Installed via                                      | Slash command                    |
| ----------------------- | -------------------------------------------------- | -------------------------------- |
| `agent-browser`         | `frontend-plugin` → `agent-browser`                | `/agent-browser:agent-browser`    |
| `remotion`              | `frontend-plugin` → `remotion-plugin`              | `/remotion-plugin:remotion`      |
| `hyperframes`           | `frontend-plugin` → `hyperframes`                  | `/hyperframes:hyperframes`       |
| `remotion-to-hyperframes` | `frontend-plugin` → `hyperframes`                | `/hyperframes:remotion-to-hyperframes` |
| `gsap`, `lottie`, …     | `frontend-plugin` → `hyperframes`                  | `/hyperframes:<skill-name>`    |
| `excalidraw-diagram`    | `core-plugin` → `excalidraw-plugin`                | `/excalidraw-plugin:excalidraw-diagram` |
| `skill-creator`         | `core-plugin` → `skill-creator`                    | `/skill-creator:skill-creator`          |
| `shadcn`                | `devops-plugin` → `vercel`                         | `/vercel:shadcn`                 |
| `next-best-practices`   | `devops-plugin` → `vercel` (`nextjs` skill)        | `/vercel:nextjs`                 |
| Vercel agent skills     | `devops-plugin` → `vercel`                         | `/vercel:*`                      |
| `app-store-screenshots` | `frontend-plugin` → `app-store-screenshots-plugin` | `/app-store-screenshots-plugin:app-store-screenshots` |
| `seo-audit`             | `marketing-plugin` → `marketing-skills`            | `/marketing-skills:seo-audit`    |
| `copywriting`           | `marketing-plugin` → `marketing-skills`            | `/marketing-skills:copywriting`  |
| `heygen` (avatar)       | `ai-tools-plugin` → `heygen`                       | `/heygen:avatar`                 |
| `heygen` (video)        | `ai-tools-plugin` → `heygen`                       | `/heygen:video`                  |
| `heygen` (translate)    | `ai-tools-plugin` → `heygen`                       | `/heygen:translate`              |
| `game-development`      | `gamedev-core`                                     | `/gamedev-core:game-development`  |
| `game-developer`        | `gamedev-core`                                     | `/gamedev-core:game-developer`    |
| `threejs-fundamentals`  | `gamedev-threejs`                                  | `/gamedev-threejs:threejs-fundamentals` |
| `webgpu-threejs-tsl`    | `gamedev-threejs`                                  | `/gamedev-threejs:webgpu-threejs-tsl`   |
| `threejs-geometry`, …   | `gamedev-threejs`                                  | `/gamedev-threejs:<skill-name>`   |
| `threejs-gameplay-systems`, … | `gamedev-threejs`                            | `/gamedev-threejs:<skill-name>`   |
| `godot`                 | `gamedev-godot`                                    | `/gamedev-godot:godot`            |
| `unity-skills`          | `gamedev-unity`                                    | `/gamedev-unity:unity-skills`     |
| `first-100-customers`   | `marketing-plugin`                                 | `/marketing-plugin:first-100-customers` |
| `ai-video-storyboard`   | `ai-video`                                         | `/ai-video:ai-video-storyboard`   |
| `ai-video-prompt-enhancer` | `ai-video`                                      | `/ai-video:ai-video-prompt-enhancer` |
| `tiktok-reel-hook-generator` | `ai-video`                                    | `/ai-video:tiktok-reel-hook-generator` |
| `video-prompting`       | `ai-video`                                         | `/ai-video:video-prompting`       |
| `visual-image`          | `ai-video`                                         | `/ai-video:visual-image`          |
| `character-design-sheet` | `ai-video`                                        | `/ai-video:character-design-sheet` |

`marketing-skills` ([marketingskills](https://github.com/coreyhaines31/marketingskills)) ships 41 skills; `marketing-plugin` depends on the whole plugin. Highlighted above: `seo-audit` and `copywriting`.

`hyperframes` ([heygen-com/hyperframes](https://github.com/heygen-com/hyperframes)) ships 15 skills — HTML-to-video, GSAP/Lottie/Three.js/WAAI animations, website capture, and Remotion migration. Highlighted above: `hyperframes`, `remotion-to-hyperframes`. Full catalog: [claudemarketplaces](https://claudemarketplaces.com/skills/heygen-com/hyperframes).

`heygen` ([heygen-com/skills](https://github.com/heygen-com/skills)) ships 11 skill entry points in the [claudemarketplaces catalog](https://claudemarketplaces.com/skills/heygen-com/skills) (`heygen`, `text-to-speech`, `video-translate`, `video-understand`, `video-edit`, `avatar-video`, `ai-video-gen`, `create-video`, `video-download`, `visual-style`, `faceswap`). The Claude plugin bundles them via `heygen@heygen` — highlighted above: `/heygen:avatar`, `/heygen:video`, `/heygen:translate`.

Game development is split by engine across four plugins: `gamedev-core` (engine-agnostic), `gamedev-threejs`, `gamedev-godot`, and `gamedev-unity`. Install only the engines you use.

`gamedev-core` bundles 2 engine-agnostic skills: `game-development` (orchestrator — game loop, pattern/AI/collision selection, performance budget; routes to ten sub-skill docs for 2D/3D, web, mobile, PC, VR/AR, design, art, audio, multiplayer) from [sickn33/agentic-awesome-skills](https://github.com/sickn33/agentic-awesome-skills), and `game-developer` (ECS, physics, netcode, 60+ FPS optimization) from [Jeffallan/claude-skills](https://github.com/Jeffallan/claude-skills). Both MIT.

`gamedev-threejs` bundles 20 Three.js skills. Low-level primitives — 11 skills: 10 from [cloudai-x/threejs-skills](https://github.com/cloudai-x/threejs-skills) ([claudemarketplaces catalog](https://claudemarketplaces.com/skills/cloudai-x/threejs-skills)) plus `webgpu-threejs-tsl` from [dgreenheck/webgpu-claude-skill](https://github.com/dgreenheck/webgpu-claude-skill). Highlighted above: `threejs-fundamentals`, `webgpu-threejs-tsl`. Full cloudai-x set: `threejs-geometry`, `threejs-materials`, `threejs-lighting`, `threejs-textures`, `threejs-animation`, `threejs-loaders`, `threejs-shaders`, `threejs-postprocessing`, `threejs-interaction`.

Game-building suite — 8 skills from [majidmanzarpour/threejs-game-skills](https://github.com/majidmanzarpour/threejs-game-skills): `threejs-gameplay-systems`, `threejs-aaa-graphics-builder`, `threejs-game-ui-designer`, `threejs-debug-profiler`, `threejs-qa-release`, plus optional API-key asset generators `threejs-3d-generator` (Tripo / `TRIPO_API_KEY`), `threejs-image-generator` (Gemini / `GEMINI_API_KEY`), and `threejs-audio-generator` (ElevenLabs / `ELEVENLABS_API_KEY`). The core game skills work without keys. (The upstream `threejs-game-director` orchestrator was dropped — `gamedev-core`'s `game-development` is the single orchestrator; its credential probe script now lives in `threejs-3d-generator/scripts/`.) **Plugin caveat:** the generators reference helper scripts via hardcoded `~/.claude/skills/<skill>/scripts/...` paths (upstream assumes a global `npx skills add -g` install); bundled as a plugin those paths resolve only if also installed globally, otherwise invoke the scripts from the plugin's own skill folders.

`gamedev-godot` bundles the `godot` skill + `/godot` command from [Randroids-Dojo/skills](https://github.com/Randroids-Dojo/skills) and wires the [godot-mcp](https://github.com/Coding-Solo/godot-mcp) server via `.mcp.json` (`npx @coding-solo/godot-mcp`, set `GODOT_PATH`). `gamedev-unity` vendors the `unity-skills` Editor-automation docs from [Besty0728/Unity-Skills](https://github.com/Besty0728/Unity-Skills); unlike Godot, Unity automation runs inside the Unity Editor and needs Unity-side setup (the UnitySkills REST bridge and/or [CoplayDev/unity-mcp](https://github.com/CoplayDev/unity-mcp), configured from Unity's own UI), so no `.mcp.json` is shipped. All four MIT.

**Overlap check:** `agent-browser` is the default CLI for browser automation (snapshot + `@eN` refs, low token cost). `playwright` MCP complements it for MCP-native tool-calling flows. `chrome-devtools-mcp` covers debugging and performance — not duplicated.

**Overlap check:** `copywriting` and `seo-audit` complement `frontend-design` (UI implementation), core `prd` (requirements), and the launch playbook bundled in `first-100-customers` (launch ops) — they do not duplicate them.

**Overlap check:** `first-100-customers` (`marketing-plugin`) is the GTM *orchestrator* — a 7-channel weekly acquisition engine. It bundles the 56-platform launch playbook (platform-by-platform launch ops, `references/launch-playbook/`) and hands off to `marketing-skills:*` (`launch`, `cold-email`, `prospecting`, `social`, `community-marketing`, `onboarding`, `referrals`, …) for per-channel depth — sequencing layer over them, not a duplicate.

**Overlap check:** [`shadcn`](https://claudemarketplaces.com/skills/shadcn/ui/shadcn) (component management via `/vercel:shadcn`) complements `frontend-design` (creative UI design) — not duplicated.

**Overlap check:** `remotion-plugin` (React programmatic video) and `hyperframes` (HTML/GSAP video) complement each other — use `/hyperframes:remotion-to-hyperframes` to bridge Remotion projects into HyperFrames. Animation adapter skills (`gsap`, `lottie`, `three`, `animejs`, `css-animations`, `waapi`, `tailwind`) are HyperFrames-specific, not duplicated by `remotion-plugin`.

**Overlap check:** `heygen` (avatar/TTS/translation via HeyGen API) complements `hyperframes` and `remotion-plugin` (programmatic video authoring) — not duplicated.

**Overlap check:** `gamedev-core` is engine-agnostic (game loop, patterns, netcode, optimization) and sits *below* the engine plugins — its `game-development` orchestrator teaches principles the engine plugins then implement, not a duplicate of them. `gamedev-threejs` Three.js skills complement `frontend-plugin` → `hyperframes` (`/hyperframes:three` for HyperFrames video) — general game/3D dev vs video-composition context. `webgpu-threejs-tsl` complements `threejs-shaders` (WebGPU/TSL vs GLSL) — not duplicated. Within `gamedev-threejs`, the cloudai-x/dgreenheck primitives (fundamentals, geometry, materials, shaders, …) teach the Three.js API, while the majidmanzarpour game-building suite (`threejs-gameplay-systems` + specialists) ships complete playable games on top of them — layered, not duplicated. `gamedev-godot` and `gamedev-unity` are separate engines — no overlap with the Three.js browser stack.

## Upstream sources

| Skill                           | Source                                                                                               |
| ------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `agent-browser`                 | [vercel-labs/agent-browser](https://github.com/vercel-labs/agent-browser) via `agent-browser@agent-browser` |
| `remotion`                      | [remotion-dev/skills](https://github.com/remotion-dev/skills) via `remotion-plugin@ai-rules`         |
| `hyperframes`, `gsap`, `lottie`, … | [heygen-com/hyperframes](https://github.com/heygen-com/hyperframes) via `hyperframes@hyperframes` ([claudemarketplaces](https://claudemarketplaces.com/skills/heygen-com/hyperframes)) |
| `heygen`, `text-to-speech`, …   | [heygen-com/skills](https://github.com/heygen-com/skills) via `heygen@heygen` ([claudemarketplaces](https://claudemarketplaces.com/skills/heygen-com/skills)) |
| `game-development`              | [sickn33/agentic-awesome-skills](https://github.com/sickn33/agentic-awesome-skills) via `gamedev-core@ai-rules` (MIT) |
| `game-developer`               | [Jeffallan/claude-skills](https://github.com/Jeffallan/claude-skills) via `gamedev-core@ai-rules` (MIT) |
| `threejs-fundamentals`, …       | [cloudai-x/threejs-skills](https://github.com/cloudai-x/threejs-skills) via `gamedev-threejs@ai-rules` ([claudemarketplaces](https://claudemarketplaces.com/skills/cloudai-x/threejs-skills)) |
| `webgpu-threejs-tsl`            | [dgreenheck/webgpu-claude-skill](https://github.com/dgreenheck/webgpu-claude-skill) via `gamedev-threejs@ai-rules` |
| `threejs-gameplay-systems`, …   | [majidmanzarpour/threejs-game-skills](https://github.com/majidmanzarpour/threejs-game-skills) via `gamedev-threejs@ai-rules` (8-skill game-building suite) |
| `godot`                        | [Randroids-Dojo/skills](https://github.com/Randroids-Dojo/skills) + [Coding-Solo/godot-mcp](https://github.com/Coding-Solo/godot-mcp) via `gamedev-godot@ai-rules` (MIT) |
| `unity-skills`                 | [Besty0728/Unity-Skills](https://github.com/Besty0728/Unity-Skills) + [CoplayDev/unity-mcp](https://github.com/CoplayDev/unity-mcp) via `gamedev-unity@ai-rules` (MIT) |
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
npx skills add https://github.com/heygen-com/skills
npx skills add https://github.com/cloudai-x/threejs-skills
npx skills add https://github.com/dgreenheck/webgpu-claude-skill --skill webgpu-threejs-tsl
npx skills add https://github.com/majidmanzarpour/threejs-game-skills --skill '*'
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
