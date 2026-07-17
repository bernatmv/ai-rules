# Plugin list

Plugins in the `ai-rules` marketplace declare dependencies in each plugin's
`.claude-plugin/plugin.json`. Installing a plugin auto-installs its dependencies.

Third-party marketplaces are registered in `.claude/settings.json` via
`extraKnownMarketplaces` (including `claude-plugins-official`) when you use this repo
as a project. For a global install outside this repo, add those marketplaces once.

> The official `claude-plugins-official` marketplace supplies most dependencies
> (`superpowers`, `github`, `figma`, `vercel`, `supabase`, …). It is usually built in,
> but add it explicitly if those deps fail with "not found in marketplace".
>
> `heygen-com/hyperframes` stores assets via **Git LFS** — install `git-lfs`
> (`brew install git-lfs && git lfs install`) first, or its marketplace clone fails.

```sh
/plugin marketplace add anthropics/claude-plugins-official
/plugin marketplace add alonw0/web-asset-generator
/plugin marketplace add anthropics/skills
/plugin marketplace add thedotmack/claude-mem
/plugin marketplace add nicobailon/visual-explainer
/plugin marketplace add max-sixty/jean-claude
/plugin marketplace add coreyhaines31/marketingskills
/plugin marketplace add vercel-labs/agent-browser
/plugin marketplace add heygen-com/hyperframes
/plugin marketplace add heygen-com/skills
/plugin marketplace add DietrichGebert/ponytail
```

Then install the plugins you need:

```sh
/plugin marketplace add bernatmv/ai-rules
/plugin install fullstack-plugin@ai-rules          # recommended — core + frontend + devops
/reload-plugins
/mcp
```

Or install individual plugins:

```sh
/plugin install core-plugin@ai-rules
/plugin install frontend-plugin@ai-rules
/plugin install devops-plugin@ai-rules
/plugin install ai-tools-plugin@ai-rules
/plugin install gamedev-core@ai-rules
/plugin install gamedev-threejs@ai-rules
/plugin install gamedev-godot@ai-rules
/plugin install gamedev-unity@ai-rules
/plugin install marketing-plugin@ai-rules
/reload-plugins
/mcp
```

Authenticate MCP-backed plugins after install:

```sh
/mcp
```

## fullstack-plugin

Recommended one-install bundle. No bundled skills — depends on `core-plugin`, `frontend-plugin`, and `devops-plugin` from this marketplace. The `gamedev-*` plugins are installed separately, per engine.

> `ai-tools-plugin` is **not** bundled: its `heygen@heygen` dependency uses a marketplace
> source type current Claude Code releases cannot install (`source type your Claude Code
> version does not support`), which would block the whole bundle. Install `ai-tools-plugin`
> separately once supported.

```sh
/plugin install fullstack-plugin@ai-rules
/reload-plugins
/mcp
```

See [fullstack-plugin/README.md](../fullstack-plugin/README.md).

## core-plugin

Everyday engineering workflows, PR tooling, documents, and third-party productivity plugins.

### Official (`claude-plugins-official`)

| Plugin               | Provides                                                      |
| -------------------- | ------------------------------------------------------------- |
| `superpowers`        | Development workflows (TDD, planning, debugging, code review) |
| `github`             | GitHub MCP integration                                        |
| `ralph-loop`         | Autonomous iteration loop (`/ralph-loop`)                     |
| `atlassian`          | Jira and Confluence MCP integration                           |
| `gitlab`             | GitLab MCP integration                                        |
| `stripe`             | Stripe MCP integration                                        |
| `huggingface-skills` | Hugging Face Hub skills and MCP                               |
| `skill-creator`      | Create, evaluate, and improve agent skills ([claudemarketplaces](https://claudemarketplaces.com/skills/anthropics/skills/skill-creator)) |
| `notion`             | Notion MCP integration                                        |

### Third-party

| Plugin              | Marketplace                    | Add marketplace                                                          |
| ------------------- | ------------------------------ | ------------------------------------------------------------------------ |
| `document-skills`   | `anthropic-agent-skills`       | `/plugin marketplace add anthropics/skills`                              |
| `claude-mem`        | `thedotmack`                   | `/plugin marketplace add thedotmack/claude-mem`                          |
| `visual-explainer`  | `visual-explainer-marketplace` | `/plugin marketplace add nicobailon/visual-explainer`                    |
| `jean-claude`       | `jean-claude`                  | `/plugin marketplace add max-sixty/jean-claude`                          |
| `ponytail`          | `ponytail`                     | `/plugin marketplace add DietrichGebert/ponytail`                        |
| `excalidraw-plugin` | `ai-rules`                     | `/plugin marketplace add bernatmv/ai-rules` (bundled with `core-plugin`) |

`skill-creator` is installed via `skill-creator@claude-plugins-official`; upstream source is [anthropics/skills](https://github.com/anthropics/skills).

Code review comes from `superpowers` (`/superpowers:requesting-code-review`, `/superpowers:receiving-code-review`); code simplification comes from `ponytail` (`/ponytail-review`, `/ponytail-audit`, `/ponytail-debt`). The official `code-review` and `code-simplifier` dependencies were removed to avoid overlapping entry points.

[`ponytail`](https://ponytail.dev/) ([DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail)) is a ruleset that guides the agent through a decision ladder (existing patterns → stdlib → native features → installed deps → one-liners → minimal new code) before writing code, aiming to avoid speculative/unnecessary code. Ships `/ponytail-review`, `/ponytail-audit`, and `/ponytail-debt` in lite/full/ultra intensity modes.

### MCP in core-plugin

| Server   | Notes                                       |
| -------- | ------------------------------------------- |
| `convex` | Convex backend MCP (`npx convex mcp start`) |

### Bundled skills (not available as plugin dependencies)

| Skill             | Purpose                                   |
| ----------------- | ----------------------------------------- |
| `babysit-pr`      | Keep PRs merge-ready                      |
| `plugin-advisor`  | Recommend Claude Code plugins             |
| `prd`             | Generate PRDs                             |
| `ralph`           | Convert PRDs to `prd.json` for Ralph runs |

TDD comes from the `superpowers` dependency — use `/superpowers:test-driven-development`. The bundled `test-driven-development` skill was removed to avoid duplicating superpowers.

## frontend-plugin

Frontend design, browser testing, Figma, and UI debugging.

### Official (`claude-plugins-official`)

| Plugin                | Provides                              |
| --------------------- | ------------------------------------- |
| `frontend-design`     | Frontend UI design guidance           |
| `playwright`          | Playwright MCP for browser automation |
| `figma`               | Figma MCP and design workflow skills  |
| `chrome-devtools-mcp` | Chrome DevTools MCP                   |

### Third-party and ai-rules

| Plugin                         | Marketplace                       | Add marketplace                                      |
| ------------------------------ | --------------------------------- | ---------------------------------------------------- |
| `web-asset-generator`          | `web-asset-generator-marketplace` | `/plugin marketplace add alonw0/web-asset-generator` |
| `agent-browser`                | `agent-browser`                   | `/plugin marketplace add vercel-labs/agent-browser`  |
| `hyperframes`                  | `hyperframes`                     | `/plugin marketplace add heygen-com/hyperframes`     |
| `remotion-plugin`              | `ai-rules`                        | bundled with `frontend-plugin`                       |
| `app-store-screenshots-plugin` | `ai-rules`                        | bundled with `frontend-plugin`                       |

`agent-browser` ([vercel-labs/agent-browser](https://github.com/vercel-labs/agent-browser)) is the default CLI for browser automation — compact accessibility-tree snapshots with `@eN` refs. Load runtime instructions via `agent-browser skills get core`. Complements `playwright` MCP (tool-calling) and `chrome-devtools-mcp` (debugging). Replaces the former `browser-use-plugin` dependency.

[`shadcn`](https://claudemarketplaces.com/skills/shadcn/ui/shadcn) is installed via `vercel@claude-plugins-official` (a `devops-plugin` dependency) — use `/vercel:shadcn`. Upstream source is [shadcn-ui/ui](https://github.com/shadcn-ui/ui). Complements `frontend-design` (creative UI design vs component management).

[`hyperframes`](https://claudemarketplaces.com/skills/heygen-com/hyperframes) ([heygen-com/hyperframes](https://github.com/heygen-com/hyperframes)) ships 15 skills: HTML-to-video compositions, GSAP/Lottie/Three.js/WAAI/CSS animation adapters, website capture, captions, voiceovers, and `remotion-to-hyperframes` for bridging Remotion projects. Complements `remotion-plugin` — not a replacement.

See [`.claude/SKILLS.md`](./SKILLS.md) for skill → plugin mapping.

### MCP in frontend-plugin

| Server       | Notes                      |
| ------------ | -------------------------- |
| `astro-docs` | Astro documentation search |

## devops-plugin

Cloud deployment and backend infrastructure.

### Official (`claude-plugins-official`)

| Plugin     | Provides                                                         |
| ---------- | ---------------------------------------------------------------- |
| `supabase` | Supabase MCP integration                                         |
| `vercel`   | Vercel MCP plus Vercel agent skills (`vercel-labs/agent-skills`) |

## ai-tools-plugin

HeyGen AI video — avatars, TTS, translation, and video generation.

> **Known limitation:** `heygen@heygen` currently fails to install — `This plugin uses a
> source type your Claude Code version does not support` (reproduced on Claude Code 2.1.156).
> The `heygen-com/skills` marketplace declares the plugin via an inline `skills` array with
> no `plugin.json`, which current CLI releases cannot install. Until that's supported,
> `ai-tools-plugin` can't be installed and is excluded from `fullstack-plugin`.

### Third-party

| Plugin   | Marketplace | Add marketplace                            |
| -------- | ----------- | ------------------------------------------ |
| `heygen` | `heygen`    | `/plugin marketplace add heygen-com/skills` |

[`heygen`](https://claudemarketplaces.com/skills/heygen-com/skills) ([heygen-com/skills](https://github.com/heygen-com/skills)) ships 11 skill entry points in the [claudemarketplaces catalog](https://claudemarketplaces.com/skills/heygen-com/skills). The Claude plugin bundles them via `heygen@heygen`:

- `/heygen:avatar` — digital identity and avatar creation
- `/heygen:video` — presenter-led video generation
- `/heygen:translate` — video translation / dubbing (175+ languages)

Requires a [HeyGen API key](https://app.heygen.com/api). Complements `frontend-plugin` video tooling (`hyperframes`, `remotion-plugin`).

## ai-video

AI video creation — storyboarding, prompting, hooks, image prompting, and character-consistency sheets. All skills are vendored in-repo (no plugin dependencies, no MCP), so `ai-video@ai-rules` installs standalone.

### ai-rules bundled

| Skill | Source |
| ----- | ------ |
| `ai-video-storyboard`, `ai-video-prompt-enhancer`, `tiktok-reel-hook-generator` | [aicontentskills](https://github.com/aicontentskills) (three repos; no upstream LICENSE) |
| `video-prompting` | [Square-Zero-Labs/video-prompting-skill](https://github.com/Square-Zero-Labs/video-prompting-skill) (Apache-2.0) — Seedance 2.0, Kling, Ovi, Sora, Veo 3, Wan 2.2, LTX-2/2.3 (Kling reference from [smixs/visual-skills](https://github.com/smixs/visual-skills), MIT) |
| `visual-image` | [smixs/visual-skills](https://github.com/smixs/visual-skills) (MIT) — vendored from upstream `image` under a clearer name |
| `character-design-sheet` | [inference-sh/skills](https://github.com/inference-sh/skills) (MIT) |

`character-design-sheet` declares `allowed-tools: Bash(belt *)`; its runnable examples need the inference.sh `belt` CLI (`npx skills add belt-sh/cli`), but it works as a reference guide without it. Use `/ai-video:<skill>`. Complements `ai-tools-plugin`, `frontend-plugin` video tooling, and `gamedev-threejs` generators. Standalone — not bundled into `fullstack-plugin`.

## gamedev-* (core / threejs / godot / unity)

Game development split by engine: an engine-agnostic core plus three engine-specific plugins. Install only the engines you use.

### ai-rules bundled

| Plugin            | Provides                                                                 |
| ----------------- | ------------------------------------------------------------------------ |
| `gamedev-core`    | 2 engine-agnostic skills — `game-development` (orchestrator: game loop, patterns, AI, collision, performance budget; routes to 2D/3D, web, mobile, PC, VR/AR, design, art, audio, multiplayer) + `game-developer` (ECS, physics, netcode, optimization); [sickn33/agentic-awesome-skills](https://github.com/sickn33/agentic-awesome-skills), [Jeffallan/claude-skills](https://github.com/Jeffallan/claude-skills) |
| `gamedev-threejs` | 20 Three.js skills — 11 low-level primitives (fundamentals, geometry, materials, GLSL/TSL shaders, animation, interaction; [cloudai-x/threejs-skills](https://github.com/cloudai-x/threejs-skills), [webgpu-threejs-tsl](https://github.com/dgreenheck/webgpu-claude-skill)) + an 8-skill game-building suite (gameplay, AAA graphics, UI, debug, QA, 3D/image/audio generators; [majidmanzarpour/threejs-game-skills](https://github.com/majidmanzarpour/threejs-game-skills)) |
| `gamedev-godot`   | `godot` skill + `/godot` command + `godot-mcp` server (`.mcp.json`, needs `GODOT_PATH`); [Randroids-Dojo/skills](https://github.com/Randroids-Dojo/skills), [Coding-Solo/godot-mcp](https://github.com/Coding-Solo/godot-mcp) |
| `gamedev-unity`   | `unity-skills` Editor-automation docs (UnitySkills REST bridge / unity-mcp); requires Unity-side setup, no `.mcp.json`; [Besty0728/Unity-Skills](https://github.com/Besty0728/Unity-Skills), [CoplayDev/unity-mcp](https://github.com/CoplayDev/unity-mcp) |

Install per engine, e.g. `/gamedev-core:game-development`, `/gamedev-threejs:threejs-fundamentals`, `/gamedev-godot:godot`. Complements `frontend-plugin` → `hyperframes` (`/hyperframes:three` for HyperFrames video contexts).

See [`.claude/SKILLS.md`](./SKILLS.md) for skill → plugin mapping.

### Manual install (official plugins, without ai-rules)

```sh
/plugin install <plugin-name>@claude-plugins-official
```

### Web asset generator

Favicons, app icons, and social sharing images (via `frontend-plugin` → `web-asset-generator`).

### Document skills

Excel, Word, PowerPoint, and PDF processing (via `core-plugin` → `document-skills`; includes the `pdf` skill).

### Claude MEM

Persistent memory across sessions (via `core-plugin` → `claude-mem`). Data lives in `~/.claude-mem`.

Alternative install:

```sh
npx claude-mem install
```

### Visual explainer

HTML diagrams, diff reviews, and plan reviews (via `core-plugin` → `visual-explainer`). Examples:

> draw a diagram of our authentication flow
> /diff-review
> /plan-review ~/docs/refactor-plan.md

### Google Workspace (Gmail, Drive, Calendar)

Provided by `core-plugin` → `jean-claude` — a skill/CLI plugin, not an MCP server.
Requires [uv](https://docs.astral.sh/uv/) (Python 3.11+).

After install, authenticate once:

```
Set up Google authentication for jean-claude
```

Or manually from the installed plugin directory:

```sh
uv run jean-claude auth
uv run jean-claude status
```

Credentials are stored in `~/.config/jean-claude/token.json`. You may see Google's
"unverified app" warning — use Advanced → Continue to proceed.

Example prompts:

```
Check my inbox for unread emails
Search Drive for quarterly reports
What's on my calendar today?
```

Also includes iMessage on macOS (optional).

## marketing-plugin

Marketing and go-to-market skills. Bundles `first-100-customers` — a YC-style brute-force GTM playbook (based on [@fin465's thread](https://x.com/fin465/status/2066589201085370482)) that runs as a repeatable **weekly** engine across 7 acquisition channels (launch-max ×3, competitor backlinks, warm outbound, UGC creators, build-in-public video, communities/shoutouts, weekly X trends).

### ai-rules bundled

| Plugin             | Provides                                                                                  |
| ------------------ | ----------------------------------------------------------------------------------------- |
| `marketing-plugin` | `first-100-customers` — 3-layer system (Growth Brief → 7-step Engine → Tracker toward 100) that generates assets, runs live web research, and flags every manual step; bundles the 56-platform launch playbook (`references/launch-playbook/`) |

### Dependency

| Plugin             | Marketplace       | Add marketplace                                         |
| ------------------ | ----------------- | ------------------------------------------------------- |
| `marketing-skills` | `marketingskills` | `/plugin marketplace add coreyhaines31/marketingskills` |

Install via `marketing-plugin@ai-rules` — use `/marketing-plugin:first-100-customers`. The engine works standalone — the 56-platform launch playbook is bundled in — and cross-references `marketing-skills:*` and optionally `ai-tools-plugin`/`frontend-plugin` video tooling when installed. Standalone — not part of `fullstack-plugin`.

See [`.claude/SKILLS.md`](./SKILLS.md) for skill → plugin mapping.

## Ralph Wiggum

Two complementary pieces:

| Piece               | Source                                  | Purpose                                           |
| ------------------- | --------------------------------------- | ------------------------------------------------- |
| `ralph` skill       | Bundled in `core-plugin/skills/`        | Convert PRDs to `prd.json` (`/core-plugin:ralph`) |
| `ralph-loop` plugin | Dependency on `claude-plugins-official` | Autonomous iteration loop (`/ralph-loop`)         |

`ralph-loop` usage:

`/ralph-loop "<prompt>" --max-iterations <n> --completion-promise "<text>"`

Example:

`/ralph-loop "Build a REST API for todos. Requirements: CRUD operations, input validation, tests. Output <promise>COMPLETE</promise> when done." --completion-promise "COMPLETE" --max-iterations 50`

Cancel with `/cancel-ralph`.

Good task definitions:

When complete:

- All CRUD endpoints working
- Input validation in place
- Tests passing (coverage > 80%)
- README with API docs
- Output: <promise>COMPLETE</promise>

```

```

Phase 1: User authentication (JWT, tests)
Phase 2: Product catalog (list/search, tests)
Phase 3: Shopping cart (add/remove, tests)

Output <promise>COMPLETE</promise> when all phases done.

```

```

Implement feature X following TDD:

1. Write failing tests
2. Implement feature
3. Run tests
4. If any fail, debug and fix
5. Refactor if needed
6. Repeat until all green
7. Output: <promise>COMPLETE</promise>

````

## Manage dependencies

List installed plugins and dependency errors:

```sh
claude plugin list
/plugin
````

Remove orphaned auto-installed dependencies:

```sh
claude plugin prune
```

Uninstall a plugin and clean up its dependencies:

```sh
claude plugin uninstall fullstack-plugin@ai-rules --prune
claude plugin uninstall core-plugin@ai-rules --prune
claude plugin uninstall frontend-plugin@ai-rules --prune
claude plugin uninstall devops-plugin@ai-rules --prune
claude plugin uninstall ai-tools-plugin@ai-rules --prune
claude plugin uninstall gamedev-core@ai-rules --prune
claude plugin uninstall gamedev-threejs@ai-rules --prune
claude plugin uninstall gamedev-godot@ai-rules --prune
claude plugin uninstall gamedev-unity@ai-rules --prune
```
