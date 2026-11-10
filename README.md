# ai-rules

A curated **Claude Code** plugin marketplace: skills, bundled official and third-party plugins, and MCP integrations for everyday engineering workflows.

## Plugins

| Plugin                                 | Description                                                                                     |
| -------------------------------------- | ----------------------------------------------------------------------------------------------- |
| [fullstack-plugin](./fullstack-plugin) | **Recommended** — bundles `core-plugin`, `frontend-plugin`, and `devops-plugin`. `roblox-gamedev` is installed separately |
| [core-plugin](./core-plugin)           | Core skills plus engineering workflows, GitHub/Jira/Notion, documents, and productivity plugins |
| [frontend-plugin](./frontend-plugin)   | Frontend design and UI polish, Figma, HyperFrames, Remotion, agent-browser, Playwright, Chrome DevTools, web assets, Astro docs MCP |
| [devops-plugin](./devops-plugin)       | Supabase and Vercel MCP integrations                                                            |
| [ai-video](./ai-video)                 | AI video creation — storyboarding, single-clip and model-specific prompting (Seedance/Kling/Veo/Sora/Wan/LTX), TikTok/Reel hooks, image prompting, character sheets |
| [roblox-gamedev](./roblox-gamedev)     | Roblox — game creation pipeline, Luau, UI, maps, 3D models, VFX, SFX, animation, economy, stud-style building, trailers, plus a 30-skill Blender stack ([SyphoDev](https://www.youtube.com/@SyphoDev), [mvvthw](https://github.com/mvvthw/roblox-claude-skills), [zriptic](https://github.com/zriptic/roclicks-skills), [RobLe3](https://github.com/RobLe3/cc-blender-skill)) |
| [marketing-plugin](./marketing-plugin) | Marketing & go-to-market skills — `first-100-customers`, a YC-style weekly GTM playbook across 7 acquisition channels with a bundled 56-platform launch playbook |

See [Installation](#installation) below, [`.claude/PLUGIN.md`](.claude/PLUGIN.md) for dependency details, and [`.claude/MCP.md`](.claude/MCP.md) for MCP setup.

## Plugin contents

### fullstack-plugin

Meta-plugin with no bundled skills. Depends on `core-plugin`, `frontend-plugin`, and `devops-plugin` — one install for the full stack. `roblox-gamedev` is installed separately.

### core-plugin

#### Bundled skills

| Skill             | Purpose                                                              |
| ----------------- | -------------------------------------------------------------------- |
| `babysit-pr`      | Keep a PR merge-ready: triage comments, resolve conflicts, fix CI    |
| `model-selection` | Starting points for choosing a model and effort by task; guidance, not hard rules |

Grilling, specs, tickets, TDD, debugging, code review, and domain modelling all come from the `mattpocock-skills` dependency — not duplicated in this repo. PDF and skill authoring come from `document-skills` and `skill-creator`.

#### Dependencies (14)

| Plugin               | Purpose                                                       |
| -------------------- | ------------------------------------------------------------- |
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
| `ponytail`           | Minimal-code ruleset — decision ladder before writing code ([ponytail.dev](https://ponytail.dev/)) |
| `mattpocock-skills`  | 25 engineering/productivity skills — grilling, spec→tickets, TDD, code review, domain modelling ([aihero.dev/skills](https://www.aihero.dev/skills)) |
| `warp`               | Native Warp terminal notifications when Claude finishes or needs input ([warpdotdev/claude-code-warp](https://github.com/warpdotdev/claude-code-warp)) |
| `excalidraw-plugin`  | Excalidraw diagram JSON (ai-rules)                            |

`skill-creator` installs via `skill-creator@claude-plugins-official` (same upstream as [anthropics/skills](https://github.com/anthropics/skills)).

[`mattpocock-skills`](https://www.aihero.dev/skills) ([mattpocock/skills](https://github.com/mattpocock/skills)) installs via `mattpocock-skills@mattpocock`. Run `/setup-matt-pocock-skills` once per repo to pick an issue tracker (GitHub/Linear/local files), triage labels, and a docs location. Its main flow is `/grill-me` or `/grill-with-docs` → `/to-spec` → `/to-tickets` → `/implement`, with `/ask-matt` as a router over the set.

[`ponytail`](https://ponytail.dev/) ([DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail)) installs via `ponytail@ponytail` and adds `/ponytail-review`, `/ponytail-audit`, and `/ponytail-debt` — code simplification and minimal-code auditing, a different axis from correctness review. Correctness review is Claude Code's built-in `/code-review`; `superpowers`, `code-review`, and `code-simplifier` were all dropped to keep one entry point per job.

#### MCP in core-plugin

| Server   | Purpose            |
| -------- | ------------------ |
| `convex` | Convex backend MCP |

### frontend-plugin

Bundled skill: [`ui-character-and-polish`](frontend-plugin/skills/ui-character-and-polish/SKILL.md) — audit user journeys and add fitting interactions, AI UI patterns, and optional sound, drawing on Interior, Beautiful UI, and Cuelume.

#### Dependencies (9)

| Plugin                         | Purpose                                                 |
| ------------------------------ | ------------------------------------------------------- |
| `frontend-design`              | Frontend UI design guidance                             |
| `playwright`                   | Playwright MCP for browser automation                   |
| `figma`                        | Figma MCP and design workflow skills                    |
| `chrome-devtools-mcp`          | Chrome DevTools MCP                                     |
| `web-asset-generator`          | Favicons, app icons, Open Graph images                  |
| `agent-browser`                | Browser automation CLI ([vercel-labs/agent-browser](https://github.com/vercel-labs/agent-browser)) |
| `hyperframes`                  | HTML-to-video, GSAP/Lottie/Three.js animations, Remotion bridge ([heygen-com/hyperframes](https://github.com/heygen-com/hyperframes)) |
| `remotion-plugin`              | Programmatic video creation — 13 Remotion skills (ai-rules) |
| `app-store-screenshots-plugin` | App Store marketing screenshots (ai-rules)              |

[`agent-browser`](https://claudemarketplaces.com/skills/vercel-labs/agent-browser/agent-browser) is the default CLI for browser automation. Complements `playwright` MCP and `chrome-devtools-mcp` — replaces the former `browser-use-plugin`.

[`shadcn`](https://claudemarketplaces.com/skills/shadcn/ui/shadcn) installs via `vercel@claude-plugins-official` (a `devops-plugin` dependency; `/vercel:shadcn`); upstream source is [shadcn-ui/ui](https://github.com/shadcn-ui/ui). Complements `frontend-design`.

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

### ai-video

#### Bundled skills (6)

AI video creation — plan, prompt, and hook short-form and cinematic AI video, plus the image and character-consistency skills that feed it. Vendored from several upstreams (attribution below); use `/ai-video:<skill>`.

| Skill | Purpose |
| ----- | ------- |
| `ai-video-storyboard` | Plan a multi-shot AI video (>15s) as a coordinated shot list with visually consistent per-segment prompts |
| `ai-video-prompt-enhancer` | Turn a rough idea into one detailed, cinematic single-clip prompt |
| `tiktok-reel-hook-generator` | Scroll-stopping 1–3s visual hooks with ready-to-copy prompts for TikTok / Reels / Shorts |
| `video-prompting` | Model-specific prompts — Seedance 2.0, Kling, Ovi, Sora, Veo 3, Wan 2.2, LTX-2/2.3 |
| `visual-image` | Image prompting for Nano Banana (NBP/NB2) and GPT Image 2.5 — storyboards, character sheets, product/UI shots |
| `character-design-sheet` | Character consistency across AI images — turnarounds, expression sheets, palettes, LoRA techniques |

Sources: [aicontentskills/ai-video-storyboard-skill](https://github.com/aicontentskills/ai-video-storyboard-skill), [aicontentskills/ai-video-prompt-enhancer](https://github.com/aicontentskills/ai-video-prompt-enhancer), [aicontentskills/tiktok-reel-hook-generator](https://github.com/aicontentskills/tiktok-reel-hook-generator) (no upstream LICENSE); [Square-Zero-Labs/video-prompting-skill](https://github.com/Square-Zero-Labs/video-prompting-skill) (Apache-2.0); [smixs/visual-skills](https://github.com/smixs/visual-skills) (MIT — its generic `image` skill is vendored as `visual-image`; its Kling reference lives in `video-prompting`); [inference-sh/skills](https://github.com/inference-sh/skills) (MIT). **Caveat:** `character-design-sheet` declares `allowed-tools: Bash(belt *)` and its runnable examples need the inference.sh `belt` CLI (`npx skills add belt-sh/cli`); as a reference guide it works without it. Complements `frontend-plugin` video tooling. Standalone — not bundled into `fullstack-plugin`.

### roblox-gamedev

44 skills and 7 worker agents for Roblox development, vendored from four upstreams. See [`roblox-gamedev/README.md`](./roblox-gamedev/README.md) for the skill list, setup, licenses, and local adaptations. Start with `/roblox-gamedev:roblox-skills-setup`, then `/roblox-gamedev:create-roblox-game`.

The plugin ships no MCP config. Add the `Roblox_Studio` and `blender` servers yourself, as described in [`.claude/MCP.md`](./.claude/MCP.md).

### marketing-plugin

#### Bundled skills (3)

| Skill | Purpose |
| ----- | ------- |
| `first-100-customers` | YC-style brute-force GTM playbook (based on [@fin465's thread](https://x.com/fin465/status/2066589201085370482)) — a repeatable **weekly** engine across 7 acquisition channels: launch-max (3×), steal competitor backlinks, warm outbound, UGC creators, build-in-public video, go where customers are, and ride weekly X trends. Runs as a 3-layer system (Growth Brief → 7-step Engine → Tracker toward 100), generating assets and live web research while flagging every manual step. Bundles the 56-platform launch playbook (launch directories, deal/LTD marketplaces, software directories) as its launch-max reference. |
| `seo-keyword-research` | Validates search phrasing, demand, and SERP fit before keywords are used in pages or campaigns. |
| `seo-strategy` | Turns search, content, technical, and company-trust findings into a prioritized organic search roadmap. |

#### Dependencies (1)

| Plugin | Marketplace | Purpose |
| ------ | ----------- | ------- |
| `marketing-skills` | `marketingskills` | Deep-dive channel skills the playbook hands off to (`launch`, `cold-email`, `prospecting`, `social`, `community-marketing`, `onboarding`, `referrals`, …) |

Use `/marketing-plugin:first-100-customers`. The engine works standalone — the 56-platform launch playbook is bundled in — and cross-references `marketing-skills:*` and (optionally) `frontend-plugin` video tooling when installed. Standalone — not bundled into `fullstack-plugin`.

## What lives here

| Path                                                                         | Role                                                     |
| ---------------------------------------------------------------------------- | -------------------------------------------------------- |
| [`CLAUDE.md`](CLAUDE.md)                                                     | Agent behavioral guidelines plus Codex/Claude Code model routing |
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
```

```sh
/plugin marketplace add DietrichGebert/ponytail
/plugin marketplace add mattpocock/skills
/plugin marketplace add warpdotdev/claude-code-warp
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
claude plugin marketplace add DietrichGebert/ponytail
claude plugin marketplace add mattpocock/skills
claude plugin marketplace add warpdotdev/claude-code-warp
claude plugin marketplace add bernatmv/ai-rules
claude plugin install fullstack-plugin@ai-rules
```

Install only what you need:

| Need                                                    | Install                     |
| ------------------------------------------------------- | --------------------------- |
| Full stack (core + frontend + devops)                   | `fullstack-plugin@ai-rules` |
| PR workflows, GitHub, Notion, documents, Google         | `core-plugin@ai-rules`      |
| UI design, Figma, browser testing, DevTools, web assets | `frontend-plugin@ai-rules`  |
| Supabase, Vercel                                        | `devops-plugin@ai-rules`    |
| Roblox game development and Blender asset work          | `roblox-gamedev@ai-rules`   |
| First 100 customers / GTM + 56-platform launch playbook | `marketing-plugin@ai-rules` |

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
   - `fullstack-plugin@ai-rules` (or individual core/frontend/devops/roblox-gamedev plugins)
2. Confirm key dependencies, for example:
   - `figma@claude-plugins-official` (frontend)
   - `vercel@claude-plugins-official` (devops)
   - `ponytail@ponytail` (core)
   - `mattpocock-skills@mattpocock` (core)
3. `/plugin` → **Errors** — should be empty. If you see `dependency-unsatisfied`, add the missing marketplace and reinstall.
4. `/reload-plugins` — check skill and MCP server counts.
5. `/mcp` — authenticate MCP services you use (Figma, GitHub, Vercel, Supabase, etc.).
6. Google Workspace — ask Claude to `Set up Google authentication for jean-claude` (requires [uv](https://docs.astral.sh/uv/)).

Optional JSON check:

```sh
claude plugin list --json | jq '.[] | select(.marketplace=="ai-rules") | {name, enabled, errors}'
```

Spot-check skills:

- Core: `/core-plugin:babysit-pr`
- Grilling / spec flow: `/grill-me`, `/to-spec`, `/to-tickets`, `/implement`
- TDD: `/tdd` — routing help: `/ask-matt`
- Figma: open a Figma URL or ask Claude to use Figma MCP (after `/mcp` auth)
- Roblox: `/roblox-gamedev:create-roblox-game` or `/roblox-gamedev:roblox-economy`
- Marketing: `/marketing-plugin:first-100-customers`
- Ponytail: `/ponytail-review`, `/ponytail-audit`, or `/ponytail-debt`

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
claude plugin uninstall roblox-gamedev@ai-rules --prune
claude plugin uninstall marketing-plugin@ai-rules --prune
```

## Creating a New Plugin

```bash
./scripts/init-plugin.sh <plugin-name>
```

## Creating a New Skill

```bash
./scripts/create-skill.sh <plugin-name> <skill-name>
```
