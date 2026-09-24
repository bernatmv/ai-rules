# frontend-plugin

Frontend design, UI polish, browser testing, and UI integration plugin for Claude Code.

## Bundled skill

[`ui-character-and-polish`](skills/ui-character-and-polish/SKILL.md) audits user journeys for useful new interface moments and refines them with interaction, depth, motion, and optional sound. It consults the live [Interior](https://www.interior.dev/docs), [Beautiful UI](https://www.beautifului.dev/), and [Cuelume](https://cuelume.dev/docs) catalogs when needed, including future additions; it checks for an official MCP before falling back to docs and registries. Use `/frontend-plugin:ui-character-and-polish` alongside `frontend-design` when building or refining a web UI.

## Dependencies

Installing `frontend-plugin@ai-rules` auto-installs:

| Plugin | Marketplace | Provides |
| --- | --- | --- |
| `frontend-design` | `claude-plugins-official` | Frontend UI design guidance |
| `playwright` | `claude-plugins-official` | Playwright MCP for browser automation |
| `figma` | `claude-plugins-official` | Figma MCP and design workflow skills |
| `chrome-devtools-mcp` | `claude-plugins-official` | Chrome DevTools MCP |
| `web-asset-generator` | `web-asset-generator-marketplace` | Favicons, app icons, Open Graph images |
| `vercel` | `claude-plugins-official` | [`shadcn`](https://claudemarketplaces.com/skills/shadcn/ui/shadcn), Next.js best practices, Vercel agent skills |
| `agent-browser` | `agent-browser` | Browser automation CLI via Chrome DevTools Protocol |
| `hyperframes` | `hyperframes` | HyperFrames HTML-to-video + 15 animation/adapter skills ([catalog](https://claudemarketplaces.com/skills/heygen-com/hyperframes)) |
| `remotion-plugin` | `ai-rules` | Programmatic video with Remotion — 12 skills (router, create, render, captions, maps, markup, studio, upgrade, …) |
| `app-store-screenshots-plugin` | `ai-rules` | App Store marketing screenshots |
| `marketing-skills` | `marketingskills` | SEO audit, copywriting, CRO, paid ads, etc. (41 skills) |

Key marketing skills: `/marketing-skills:seo-audit`, `/marketing-skills:copywriting`. See [`.claude/SKILLS.md`](../.claude/SKILLS.md).

Browser automation: use `agent-browser` CLI by default (`/agent-browser:agent-browser`, or `agent-browser skills get core`). `playwright` MCP complements it for MCP-native flows; `chrome-devtools-mcp` covers debugging and performance.

shadcn/ui: use `/vercel:shadcn` (via `vercel@claude-plugins-official`). Upstream: [shadcn-ui/ui](https://github.com/shadcn-ui/ui) — [claudemarketplaces](https://claudemarketplaces.com/skills/shadcn/ui/shadcn). Complements `frontend-design`.

Video: `remotion-plugin` for React/Remotion (`/remotion-plugin:remotion`); `hyperframes` for HTML/GSAP video (`/hyperframes:hyperframes`). Bridge Remotion → HyperFrames with `/hyperframes:remotion-to-hyperframes`. Animation adapters: `/hyperframes:gsap`, `/hyperframes:lottie`, `/hyperframes:three`, and others — see [claudemarketplaces catalog](https://claudemarketplaces.com/skills/heygen-com/hyperframes).

## MCP servers

| Server | Transport | Notes |
| --- | --- | --- |
| `astro-docs` | http | Astro documentation search |

Authenticate MCP servers after install with `/mcp`.

## Install

```sh
/plugin marketplace add coreyhaines31/marketingskills
/plugin marketplace add vercel-labs/agent-browser
/plugin marketplace add heygen-com/hyperframes
/plugin marketplace add bernatmv/ai-rules
/plugin install frontend-plugin@ai-rules
/reload-plugins
/mcp
```
