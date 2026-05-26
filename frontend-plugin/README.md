# frontend-plugin

Frontend design, browser testing, and UI integration plugin for Claude Code.

## Dependencies

Installing `frontend-plugin@ai-rules` auto-installs:

| Plugin | Marketplace | Provides |
| --- | --- | --- |
| `frontend-design` | `claude-plugins-official` | Frontend UI design guidance |
| `playwright` | `claude-plugins-official` | Playwright MCP for browser automation |
| `figma` | `claude-plugins-official` | Figma MCP and design workflow skills |
| `chrome-devtools-mcp` | `claude-plugins-official` | Chrome DevTools MCP |
| `web-asset-generator` | `web-asset-generator-marketplace` | Favicons, app icons, Open Graph images |

## MCP servers

| Server | Transport | Notes |
| --- | --- | --- |
| `astro-docs` | http | Astro documentation search |

Authenticate MCP servers after install with `/mcp`.

## Install

```sh
/plugin marketplace add bernatmv/ai-rules
/plugin install frontend-plugin@ai-rules
/reload-plugins
/mcp
```
