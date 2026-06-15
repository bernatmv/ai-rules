# ai-rules

A curated **Claude Code** plugin marketplace: skills, bundled official and third-party plugins, and MCP integrations for everyday engineering workflows.

## Plugins

| Plugin                                 | Description                                                                                     |
| -------------------------------------- | ----------------------------------------------------------------------------------------------- |
| [fullstack-plugin](./fullstack-plugin) | **Recommended** — bundles `core-plugin`, `frontend-plugin`, `devops-plugin`, and `gamedev-plugin`. `ai-tools-plugin` is installed separately (see [note](#ai-tools-plugin)) |
| [core-plugin](./core-plugin)           | Core skills plus engineering workflows, GitHub/Jira/Notion, documents, and productivity plugins |
| [frontend-plugin](./frontend-plugin)   | Frontend design, Figma, HyperFrames, Remotion, agent-browser, Playwright, Chrome DevTools, web assets, marketing copy & SEO, Astro docs MCP |
| [devops-plugin](./devops-plugin)       | Supabase and Vercel MCP integrations                                                            |
| [ai-tools-plugin](./ai-tools-plugin)   | HeyGen AI video — avatars, TTS, translation, video generation, and editing                      |
| [gamedev-plugin](./gamedev-plugin)     | Three.js and WebGPU 3D skills plus a full game-building suite ([cloudai-x/threejs-skills](https://github.com/cloudai-x/threejs-skills), [webgpu-threejs-tsl](https://github.com/dgreenheck/webgpu-claude-skill), [majidmanzarpour/threejs-game-skills](https://github.com/majidmanzarpour/threejs-game-skills)) |

See [Installation](#installation) below, [`.claude/PLUGIN.md`](.claude/PLUGIN.md) for dependency details, and [`.claude/MCP.md`](.claude/MCP.md) for MCP setup.

## Plugin contents

### fullstack-plugin

Meta-plugin with no bundled skills. Depends on `core-plugin`, `frontend-plugin`, `devops-plugin`, and `gamedev-plugin` — one install for the full stack.

> **Note:** `ai-tools-plugin` (HeyGen) is intentionally **not** bundled here. Its `heygen@heygen` dependency uses a marketplace source type that current Claude Code releases cannot install (`This plugin uses a source type your Claude Code version does not support`), which would otherwise block the whole `fullstack-plugin` install. Install it on its own once your Claude Code version supports it — see [ai-tools-plugin](#ai-tools-plugin).

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
| `skill-creator`      | Create and improve agent skills ([claudemarketplaces](https://claudemarketplaces.com/skills/anthropics/skills/skill-creator)) |
| `notion`             | Notion MCP                                                    |
| `document-skills`    | Excel, Word, PowerPoint, PDF processing                       |
| `claude-mem`         | Persistent memory across sessions                             |
| `visual-explainer`   | HTML diagrams, diff reviews, plan reviews                     |
| `jean-claude`        | Gmail, Google Drive, and Google Calendar (OAuth)              |
| `excalidraw-plugin`  | Excalidraw diagram JSON (ai-rules)                            |
| `find-skills-plugin` | Discover and install skills from skills.sh (ai-rules)         |

`find-skills` complements `plugin-advisor` (marketplace plugins) and [`skill-creator`](https://claudemarketplaces.com/skills/anthropics/skills/skill-creator) (authoring) — it searches the open skills ecosystem via [skills.sh](https://skills.sh/). `skill-creator` installs via `skill-creator@claude-plugins-official` (same upstream as [anthropics/skills](https://github.com/anthropics/skills)).

#### MCP in core-plugin

| Server   | Purpose            |
| -------- | ------------------ |
| `convex` | Convex backend MCP |

### frontend-plugin

#### Dependencies (11)

| Plugin                         | Purpose                                                 |
| ------------------------------ | ------------------------------------------------------- |
| `frontend-design`              | Frontend UI design guidance                             |
| `playwright`                   | Playwright MCP for browser automation                   |
| `figma`                        | Figma MCP and design workflow skills                    |
| `chrome-devtools-mcp`          | Chrome DevTools MCP                                     |
| `web-asset-generator`          | Favicons, app icons, Open Graph images                  |
| `vercel`                       | shadcn ([claudemarketplaces](https://claudemarketplaces.com/skills/shadcn/ui/shadcn)), Next.js best practices, Vercel agent skills |
| `agent-browser`                | Browser automation CLI ([vercel-labs/agent-browser](https://github.com/vercel-labs/agent-browser)) |
| `hyperframes`                  | HTML-to-video, GSAP/Lottie/Three.js animations, Remotion bridge ([heygen-com/hyperframes](https://github.com/heygen-com/hyperframes)) |
| `remotion-plugin`              | Programmatic video creation (ai-rules)                  |
| `app-store-screenshots-plugin` | App Store marketing screenshots (ai-rules)              |
| `marketing-skills`             | SEO audit, copywriting, CRO, paid ads, etc. (41 skills) |

Marketing skills from [`marketingskills`](https://github.com/coreyhaines31/marketingskills) — includes [`seo-audit`](https://claudemarketplaces.com/skills/coreyhaines31/marketingskills/seo-audit) and [`copywriting`](https://claudemarketplaces.com/skills/coreyhaines31/marketingskills/copywriting). Complements (does not duplicate) `frontend-design`, core `prd`, and core `launch-playbook`.

[`agent-browser`](https://claudemarketplaces.com/skills/vercel-labs/agent-browser/agent-browser) is the default CLI for browser automation. Complements `playwright` MCP and `chrome-devtools-mcp` — replaces the former `browser-use-plugin`.

[`shadcn`](https://claudemarketplaces.com/skills/shadcn/ui/shadcn) installs via `vercel@claude-plugins-official` (`/vercel:shadcn`); upstream source is [shadcn-ui/ui](https://github.com/shadcn-ui/ui). Complements `frontend-design`.

[`hyperframes`](https://claudemarketplaces.com/skills/heygen-com/hyperframes) ships 15 skills for HTML-to-video (GSAP, Lottie, Three.js, WAAI, captions, voiceovers). Complements `remotion-plugin` — use `/hyperframes:remotion-to-hyperframes` to bridge Remotion projects.

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

### ai-tools-plugin

#### Dependencies (1)

| Plugin   | Purpose                                                                                          |
| -------- | ------------------------------------------------------------------------------------------------ |
| `heygen` | HeyGen avatar videos, TTS, translation, video generation, and editing ([heygen-com/skills](https://github.com/heygen-com/skills)) |

The [heygen-com/skills catalog](https://claudemarketplaces.com/skills/heygen-com/skills) lists 11 skill entry points. The Claude plugin bundles them via `heygen@heygen` — use `/heygen:avatar`, `/heygen:video`, and `/heygen:translate`. Requires a [HeyGen API key](https://app.heygen.com/api). Complements `frontend-plugin` video tooling (`hyperframes`, `remotion-plugin`).

> **Known limitation:** the `heygen@heygen` plugin currently fails to install with `This plugin uses a source type your Claude Code version does not support` (reproduced on Claude Code 2.1.156 — the `heygen-com/skills` marketplace declares the plugin via an inline `skills` array with no `plugin.json`). Until a Claude Code release supports that format, `ai-tools-plugin` cannot be installed, so it is **not** part of `fullstack-plugin`. The rest of the stack (`core`, `frontend`, `devops`, `gamedev`) is unaffected.

### gamedev-plugin

#### Bundled skills (20)

**Low-level primitives (11)** — from [cloudai-x/threejs-skills](https://github.com/cloudai-x/threejs-skills) ([claudemarketplaces catalog](https://claudemarketplaces.com/skills/cloudai-x/threejs-skills)) and [dgreenheck/webgpu-claude-skill](https://github.com/dgreenheck/webgpu-claude-skill):

| Skill | Purpose |
| ----- | ------- |
| `threejs-fundamentals` | Scene, camera, renderer, Object3D hierarchy |
| `threejs-geometry` | Shapes, BufferGeometry, instancing |
| `threejs-materials` | PBR, standard/phong materials, shaders |
| `threejs-lighting` | Lights, shadows, environment lighting |
| `threejs-textures` | Textures, UV mapping, render targets |
| `threejs-animation` | Keyframe, skeletal, morph target animation |
| `threejs-loaders` | GLTF/GLB, async loading, caching |
| `threejs-shaders` | GLSL, ShaderMaterial, custom effects |
| `threejs-postprocessing` | EffectComposer, bloom, DOF, custom passes |
| `threejs-interaction` | Raycasting, controls, user input |
| `webgpu-threejs-tsl` | WebGPU renderer, TSL node materials, compute shaders |

**Game-building suite (9)** — from [majidmanzarpour/threejs-game-skills](https://github.com/majidmanzarpour/threejs-game-skills); start with `threejs-game-director`, which routes to the specialists:

| Skill | Purpose |
| ----- | ------- |
| `threejs-game-director` | Entrypoint — orchestrates full game builds, premium iteration, phase routing |
| `threejs-gameplay-systems` | Playable slices, Vite/TS scaffold, loop, entities, input, physics, game feel |
| `threejs-aaa-graphics-builder` | Prototype→AAA visuals, models, materials, lighting, VFX, visual scorecard |
| `threejs-game-ui-designer` | HUDs, menus, overlays, responsive layout, safe areas, touch UI |
| `threejs-debug-profiler` | Runtime/loading/resize/mobile bugs, draw calls, triangles, memory, perf |
| `threejs-qa-release` | Production builds, browser/mobile verification, canvas pixels, release reports |
| `threejs-3d-generator` | Tripo text/image→3D, GLB/FBX, rigging, animation (optional `TRIPO_API_KEY`) |
| `threejs-image-generator` | Gemini concepts, textures, skies, decals, icons, GUI art (optional `GEMINI_API_KEY`) |
| `threejs-audio-generator` | ElevenLabs SFX, ambience, UI sounds, voice/TTS (optional `ELEVENLABS_API_KEY`) |

The core game skills work without API keys. **Plugin caveat:** the generators and director reference helper scripts via hardcoded `~/.claude/skills/<skill>/scripts/...` paths (upstream assumes a global `npx skills add -g` install); bundled as a plugin those resolve only if also installed globally, otherwise invoke the scripts from the plugin's skill folders.

Use `/gamedev-plugin:threejs-fundamentals` or `/gamedev-plugin:threejs-game-director` (and other skill names). Complements `frontend-plugin` → `hyperframes` (`/hyperframes:three` for HyperFrames video contexts). `webgpu-threejs-tsl` complements `threejs-shaders` (WebGPU/TSL vs GLSL).

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

**Prerequisite for HyperFrames:** install [Git LFS](https://git-lfs.com/) and run `git lfs install` **before** adding the `heygen-com/hyperframes` marketplace. That repo stores assets via Git LFS; without it the clone fails with `git-lfs: command not found` and `frontend-plugin` / `fullstack-plugin` cannot be satisfied. On macOS: `brew install git-lfs && git lfs install`.

**Prerequisite for Google Workspace:** install [uv](https://docs.astral.sh/uv/) before using the `jean-claude` dependency (via `core-plugin` or `fullstack-plugin`).

### Global install (recommended)

Use this when you want plugins available in **every project** on your machine (user scope).

Run once from any directory:

```sh
/plugin marketplace add anthropics/claude-plugins-official
```

```sh
/plugin marketplace add alonw0/web-asset-generator
```

```sh
/plugin marketplace add anthropics/skills
```

```sh
/plugin marketplace add thedotmack/claude-mem
```

```sh
/plugin marketplace add nicobailon/visual-explainer
```

```sh
/plugin marketplace add max-sixty/jean-claude
```

```sh
/plugin marketplace add coreyhaines31/marketingskills
```

```sh
/plugin marketplace add vercel-labs/agent-browser
```

```sh
/plugin marketplace add heygen-com/hyperframes
```

```sh
/plugin marketplace add heygen-com/skills
```

```sh
/plugin marketplace add bernatmv/ai-rules
```

```sh
/plugin install fullstack-plugin@ai-rules
```

```sh
/reload-plugins
```

```sh
/mcp
```

Equivalent CLI:

```sh
claude plugin marketplace add anthropics/claude-plugins-official
claude plugin marketplace add alonw0/web-asset-generator
claude plugin marketplace add anthropics/skills
claude plugin marketplace add thedotmack/claude-mem
claude plugin marketplace add nicobailon/visual-explainer
claude plugin marketplace add max-sixty/jean-claude
claude plugin marketplace add coreyhaines31/marketingskills
claude plugin marketplace add vercel-labs/agent-browser
claude plugin marketplace add heygen-com/hyperframes
claude plugin marketplace add heygen-com/skills
claude plugin marketplace add bernatmv/ai-rules
claude plugin install fullstack-plugin@ai-rules
```

Install only what you need:

| Need                                                    | Install                     |
| ------------------------------------------------------- | --------------------------- |
| Full stack (core + frontend + devops + gamedev)         | `fullstack-plugin@ai-rules` |
| PR workflows, GitHub, Notion, documents, Google         | `core-plugin@ai-rules`      |
| UI design, Figma, browser testing, DevTools, web assets, marketing copy & SEO | `frontend-plugin@ai-rules`  |
| Supabase, Vercel                                        | `devops-plugin@ai-rules`    |
| HeyGen avatars, TTS, video translation & generation     | `ai-tools-plugin@ai-rules`  |
| Three.js game and 3D development                        | `gamedev-plugin@ai-rules`   |

### Project / local install

Use this when plugins should be tied to **this repository** — for team defaults or when developing the marketplace itself.

| Scope       | Who gets it                                        | When to use                                       |
| ----------- | -------------------------------------------------- | ------------------------------------------------- |
| **Project** | Everyone who clones the repo and trusts the folder | Team-shared plugin set in `.claude/settings.json` |
| **Local**   | Only you, only in this repo checkout               | Personal overrides while working in ai-rules      |

If you clone this repo and trust the project folder, [`.claude/settings.json`](.claude/settings.json) registers third-party marketplaces via `extraKnownMarketplaces` — skip the third-party marketplace steps from the global install section above.

```sh
/plugin marketplace add bernatmv/ai-rules
```

```sh
/plugin install fullstack-plugin@ai-rules --scope project
```

```sh
/reload-plugins
```

```sh
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
   - `fullstack-plugin@ai-rules` (or individual core/frontend/devops/ai-tools/gamedev plugins)
2. Confirm key dependencies, for example:
   - `superpowers@claude-plugins-official` (core)
   - `figma@claude-plugins-official` (frontend)
   - `vercel@claude-plugins-official` (devops)
   - `heygen@heygen` (ai-tools — only if you installed `ai-tools-plugin` separately)
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
- AI tools: `/heygen:avatar` or `/heygen:video` (requires `ai-tools-plugin` + HeyGen API key)
- Gamedev: `/gamedev-plugin:threejs-fundamentals` or `/gamedev-plugin:webgpu-threejs-tsl`

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
claude plugin uninstall ai-tools-plugin@ai-rules --prune
claude plugin uninstall gamedev-plugin@ai-rules --prune
```

## Creating a New Plugin

```bash
./scripts/init-plugin.sh <plugin-name>
```

## Creating a New Skill

```bash
./scripts/create-skill.sh <plugin-name> <skill-name>
```
