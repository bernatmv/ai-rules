# devops-plugin

Cloud deployment and backend infrastructure plugin for Claude Code.

## Dependencies

Installing `devops-plugin@ai-rules` auto-installs:

| Plugin | Marketplace | Provides |
| --- | --- | --- |
| `supabase` | `claude-plugins-official` | Supabase MCP integration |
| `vercel` | `claude-plugins-official` | Vercel MCP integration |

Authenticate MCP servers after install with `/mcp`.

## Install

```sh
/plugin marketplace add bernatmv/ai-rules
/plugin install devops-plugin@ai-rules
/reload-plugins
/mcp
```
