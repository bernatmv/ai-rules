# fullstack-plugin

One-install bundle for the full `ai-rules` stack. Installing `fullstack-plugin@ai-rules` auto-installs:

| Plugin | Provides |
| --- | --- |
| `core-plugin` | Engineering workflows, GitHub/Jira/Notion, documents, Google Workspace, productivity plugins |
| `frontend-plugin` | Frontend design, Figma, HyperFrames, Remotion, agent-browser, Playwright, Chrome DevTools, web assets, marketing copy & SEO, Astro docs MCP |
| `devops-plugin` | Supabase and Vercel MCP integrations |

> The `gamedev-*` plugins (`gamedev-core`, `gamedev-threejs`, `gamedev-godot`, `gamedev-unity`) are **not** bundled — install per engine, e.g. `/plugin install gamedev-threejs@ai-rules`.
>
> `ai-tools-plugin` (HeyGen) is **not** bundled — its `heygen@heygen` dependency uses a source type current Claude Code releases cannot install, which would block the whole bundle. Install it separately once supported: `/plugin install ai-tools-plugin@ai-rules`.

## Install

```sh
# Official marketplace (usually built in; add if superpowers/figma/etc. fail with "not found")
/plugin marketplace add anthropics/claude-plugins-official

# Third-party marketplaces required by core-plugin and frontend-plugin (one-time)
# heygen-com/hyperframes needs Git LFS: brew install git-lfs && git lfs install
/plugin marketplace add alonw0/web-asset-generator
/plugin marketplace add anthropics/skills
/plugin marketplace add thedotmack/claude-mem
/plugin marketplace add nicobailon/visual-explainer
/plugin marketplace add max-sixty/jean-claude
/plugin marketplace add coreyhaines31/marketingskills
/plugin marketplace add vercel-labs/agent-browser
/plugin marketplace add heygen-com/hyperframes
/plugin marketplace add DietrichGebert/ponytail

/plugin marketplace add bernatmv/ai-rules
/plugin install fullstack-plugin@ai-rules
/reload-plugins
/mcp
```

Install individual plugins instead when you only need part of the stack — see the [root README](../README.md).
