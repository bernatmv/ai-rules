# Plugin list

Plugins in the `ai-rules` marketplace declare dependencies in each plugin's
`.claude-plugin/plugin.json`. Installing a plugin auto-installs its dependencies.

Third-party marketplaces are registered in `.claude/settings.json` via
`extraKnownMarketplaces` (including `claude-plugins-official`) when you use this repo
as a project. For a global install outside this repo, add those marketplaces once.

> The official `claude-plugins-official` marketplace supplies most dependencies
> (`figma`, `vercel`, `supabase`, …). It is usually built in,
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
/plugin marketplace add DietrichGebert/ponytail
/plugin marketplace add mattpocock/skills
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
/plugin install gamedev-core@ai-rules
/plugin install gamedev-threejs@ai-rules
/plugin install gamedev-godot@ai-rules
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
| `mattpocock-skills` | `mattpocock`                   | `/plugin marketplace add mattpocock/skills`                              |
| `excalidraw-plugin` | `ai-rules`                     | `/plugin marketplace add bernatmv/ai-rules` (bundled with `core-plugin`) |

`skill-creator` is installed via `skill-creator@claude-plugins-official`; upstream source is [anthropics/skills](https://github.com/anthropics/skills).

[`mattpocock-skills`](https://www.aihero.dev/skills) ([mattpocock/skills](https://github.com/mattpocock/skills)) ships 25 engineering and productivity skills. Run `/setup-matt-pocock-skills` once per repo to choose an issue tracker (GitHub, Linear, or local files), triage labels, and a docs location. Main flow: `/grill-me` or `/grill-with-docs` → `/to-spec` → `/to-tickets` → `/implement`; `/ask-matt` routes to the right one.

Code simplification comes from `ponytail` (`/ponytail-review`, `/ponytail-audit`, `/ponytail-debt`); correctness review is Claude Code's built-in `/code-review`. The `superpowers`, `code-review`, and `code-simplifier` dependencies were removed to keep one entry point per job — `superpowers` in particular duplicated `mattpocock-skills` on TDD, debugging, planning, brainstorming, code review, and skill authoring.

[`ponytail`](https://ponytail.dev/) ([DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail)) is a ruleset that guides the agent through a decision ladder (existing patterns → stdlib → native features → installed deps → one-liners → minimal new code) before writing code, aiming to avoid speculative/unnecessary code. Ships `/ponytail-review`, `/ponytail-audit`, and `/ponytail-debt` in lite/full/ultra intensity modes.

### MCP in core-plugin

| Server   | Notes                                       |
| -------- | ------------------------------------------- |
| `convex` | Convex backend MCP (`npx convex mcp start`) |

### Bundled skills (not available as plugin dependencies)

| Skill        | Purpose              |
| ------------ | -------------------- |
| `babysit-pr` | Keep PRs merge-ready |

TDD, grilling, specs, tickets, debugging, and code review come from the `mattpocock-skills` dependency — `/tdd`, `/grill-me`, `/to-spec`, `/to-tickets`, `/implement`. The bundled `prd`, `ralph`, and `plugin-advisor` skills were removed: the first two duplicated `/to-spec` and `/to-tickets`, and `plugin-advisor` only fired passively.

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
| `remotion-plugin`              | `ai-rules`                        | bundled with `frontend-plugin` (12 Remotion skills)  |
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

## ai-video

AI video creation — storyboarding, prompting, hooks, image prompting, and character-consistency sheets. All skills are vendored in-repo (no plugin dependencies, no MCP), so `ai-video@ai-rules` installs standalone.

### ai-rules bundled

| Skill | Source |
| ----- | ------ |
| `ai-video-storyboard`, `ai-video-prompt-enhancer`, `tiktok-reel-hook-generator` | [aicontentskills](https://github.com/aicontentskills) (three repos; no upstream LICENSE) |
| `video-prompting` | [Square-Zero-Labs/video-prompting-skill](https://github.com/Square-Zero-Labs/video-prompting-skill) (Apache-2.0) — Seedance 2.0, Kling, Ovi, Sora, Veo 3, Wan 2.2, LTX-2/2.3 (Kling reference from [smixs/visual-skills](https://github.com/smixs/visual-skills), MIT) |
| `visual-image` | [smixs/visual-skills](https://github.com/smixs/visual-skills) (MIT) — vendored from upstream `image` under a clearer name |
| `character-design-sheet` | [inference-sh/skills](https://github.com/inference-sh/skills) (MIT) |

`character-design-sheet` declares `allowed-tools: Bash(belt *)`; its runnable examples need the inference.sh `belt` CLI (`npx skills add belt-sh/cli`), but it works as a reference guide without it. Use `/ai-video:<skill>`. Complements `frontend-plugin` video tooling and `gamedev-threejs` generators. Standalone — not bundled into `fullstack-plugin`.

## gamedev-* (core / threejs / godot)

Game development split by engine: an engine-agnostic core plus two engine-specific plugins. Install only the engines you use.

### ai-rules bundled

| Plugin            | Provides                                                                 |
| ----------------- | ------------------------------------------------------------------------ |
| `gamedev-core`    | 11 engine-agnostic skills — `game-developer` (ECS, physics, netcode, optimization, patterns) plus per-platform skills `2d-games`, `3d-games`, `web-games`, `mobile-games`, `pc-games`, `vr-ar`, `game-design`, `game-art`, `game-audio`, `multiplayer`; [sickn33/agentic-awesome-skills](https://github.com/sickn33/agentic-awesome-skills), [Jeffallan/claude-skills](https://github.com/Jeffallan/claude-skills). The upstream `game-development` orchestrator was dropped — it duplicated `game-developer`, and its platform docs are now top-level skills |
| `gamedev-threejs` | 20 Three.js skills — 11 low-level primitives (fundamentals, geometry, materials, GLSL/TSL shaders, animation, interaction; [cloudai-x/threejs-skills](https://github.com/cloudai-x/threejs-skills), [webgpu-threejs-tsl](https://github.com/dgreenheck/webgpu-claude-skill)) + an 8-skill game-building suite (gameplay, AAA graphics, UI, debug, QA, 3D/image/audio generators; [majidmanzarpour/threejs-game-skills](https://github.com/majidmanzarpour/threejs-game-skills)) |
| `gamedev-godot`   | `godot` skill + `/godot` command + `godot-mcp` server (`.mcp.json`, needs `GODOT_PATH`); [Randroids-Dojo/skills](https://github.com/Randroids-Dojo/skills), [Coding-Solo/godot-mcp](https://github.com/Coding-Solo/godot-mcp) |

Install per engine, e.g. `/gamedev-core:game-developer`, `/gamedev-threejs:threejs-fundamentals`, `/gamedev-godot:godot`. Complements `frontend-plugin` → `hyperframes` (`/hyperframes:three` for HyperFrames video contexts).

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

Install via `marketing-plugin@ai-rules` — use `/marketing-plugin:first-100-customers`. The engine works standalone — the 56-platform launch playbook is bundled in — and cross-references `marketing-skills:*` and optionally `frontend-plugin` video tooling when installed. Standalone — not part of `fullstack-plugin`.

See [`.claude/SKILLS.md`](./SKILLS.md) for skill → plugin mapping.

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
claude plugin uninstall gamedev-core@ai-rules --prune
claude plugin uninstall gamedev-threejs@ai-rules --prune
claude plugin uninstall gamedev-godot@ai-rules --prune
```
