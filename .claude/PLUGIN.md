# Plugin list

Plugins in the `ai-rules` marketplace declare dependencies in each plugin's
`.claude-plugin/plugin.json`. Installing a plugin auto-installs its dependencies.

Third-party marketplaces are registered in `.claude/settings.json` via
`extraKnownMarketplaces` when you use this repo as a project. For a global install
outside this repo, add those marketplaces once:

```sh
/plugin marketplace add alonw0/web-asset-generator
/plugin marketplace add anthropics/skills
/plugin marketplace add thedotmack/claude-mem
/plugin marketplace add nicobailon/visual-explainer
/plugin marketplace add max-sixty/jean-claude
/plugin marketplace add coreyhaines31/marketingskills
/plugin marketplace add vercel-labs/agent-browser
/plugin marketplace add heygen-com/hyperframes
/plugin marketplace add heygen-com/skills
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
/plugin install gamedev-plugin@ai-rules
/reload-plugins
/mcp
```

Authenticate MCP-backed plugins after install:

```sh
/mcp
```

## fullstack-plugin

Recommended one-install bundle. No bundled skills — depends on `core-plugin`, `frontend-plugin`, `devops-plugin`, `ai-tools-plugin`, and `gamedev-plugin` from this marketplace.

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
| `code-review`        | PR and code review agents                                     |
| `code-simplifier`    | Code simplification workflows                                 |
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
| `excalidraw-plugin` | `ai-rules`                     | `/plugin marketplace add bernatmv/ai-rules` (bundled with `core-plugin`) |
| `find-skills-plugin` | `ai-rules`                  | bundled with `core-plugin` |

`find-skills` ([vercel-labs/skills](https://github.com/vercel-labs/skills)) searches [skills.sh](https://skills.sh/) for installable agent skills. Complements `plugin-advisor` (marketplace plugins) and [`skill-creator`](https://claudemarketplaces.com/skills/anthropics/skills/skill-creator) (authoring) — no overlap. `skill-creator` is installed via `skill-creator@claude-plugins-official`; upstream source is [anthropics/skills](https://github.com/anthropics/skills).

### MCP in core-plugin

| Server   | Notes                                       |
| -------- | ------------------------------------------- |
| `convex` | Convex backend MCP (`npx convex mcp start`) |

### Bundled skills (not available as plugin dependencies)

| Skill             | Purpose                                   |
| ----------------- | ----------------------------------------- |
| `babysit-pr`      | Keep PRs merge-ready                      |
| `launch-playbook` | Multi-platform product launch campaigns   |
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
| `vercel`                       | `claude-plugins-official`         | built-in — [`shadcn`](https://claudemarketplaces.com/skills/shadcn/ui/shadcn), Next.js, Vercel agent skills |
| `agent-browser`                | `agent-browser`                   | `/plugin marketplace add vercel-labs/agent-browser`  |
| `hyperframes`                  | `hyperframes`                     | `/plugin marketplace add heygen-com/hyperframes`     |
| `remotion-plugin`              | `ai-rules`                        | bundled with `frontend-plugin`                       |
| `app-store-screenshots-plugin` | `ai-rules`                        | bundled with `frontend-plugin`                       |
| `marketing-skills`             | `marketingskills`                 | `/plugin marketplace add coreyhaines31/marketingskills` |

`agent-browser` ([vercel-labs/agent-browser](https://github.com/vercel-labs/agent-browser)) is the default CLI for browser automation — compact accessibility-tree snapshots with `@eN` refs. Load runtime instructions via `agent-browser skills get core`. Complements `playwright` MCP (tool-calling) and `chrome-devtools-mcp` (debugging). Replaces the former `browser-use-plugin` dependency.

`marketing-skills` includes [`seo-audit`](https://claudemarketplaces.com/skills/coreyhaines31/marketingskills/seo-audit) and [`copywriting`](https://claudemarketplaces.com/skills/coreyhaines31/marketingskills/copywriting) plus 39 other marketing skills. Complements `frontend-design`, core `prd`, and core `launch-playbook`.

[`shadcn`](https://claudemarketplaces.com/skills/shadcn/ui/shadcn) is installed via `vercel@claude-plugins-official` — use `/vercel:shadcn`. Upstream source is [shadcn-ui/ui](https://github.com/shadcn-ui/ui). Complements `frontend-design` (creative UI design vs component management).

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

### Third-party

| Plugin   | Marketplace | Add marketplace                            |
| -------- | ----------- | ------------------------------------------ |
| `heygen` | `heygen`    | `/plugin marketplace add heygen-com/skills` |

[`heygen`](https://claudemarketplaces.com/skills/heygen-com/skills) ([heygen-com/skills](https://github.com/heygen-com/skills)) ships 11 skill entry points in the [claudemarketplaces catalog](https://claudemarketplaces.com/skills/heygen-com/skills). The Claude plugin bundles them via `heygen@heygen`:

- `/heygen:avatar` — digital identity and avatar creation
- `/heygen:video` — presenter-led video generation
- `/heygen:translate` — video translation / dubbing (175+ languages)

Requires a [HeyGen API key](https://app.heygen.com/api). Complements `frontend-plugin` video tooling (`hyperframes`, `remotion-plugin`).

## gamedev-plugin

Three.js game and 3D development skills bundled from [cloudai-x/threejs-skills](https://github.com/cloudai-x/threejs-skills).

### ai-rules bundled

| Plugin           | Provides                                                                 |
| ---------------- | ------------------------------------------------------------------------ |
| `gamedev-plugin` | 11 Three.js skills — fundamentals, geometry, materials, GLSL/TSL shaders, animation, interaction ([cloudai-x/threejs-skills](https://github.com/cloudai-x/threejs-skills), [webgpu-threejs-tsl](https://github.com/dgreenheck/webgpu-claude-skill)) |

Skills install via `gamedev-plugin@ai-rules` — use `/gamedev-plugin:threejs-fundamentals`, `/gamedev-plugin:webgpu-threejs-tsl`, etc. Complements `frontend-plugin` → `hyperframes` (`/hyperframes:three` for HyperFrames video contexts).

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
claude plugin uninstall gamedev-plugin@ai-rules --prune
```
