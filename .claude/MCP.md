# Found at

`~/.claude.json`

# List all configured servers

`claude mcp list`

# Get details for a specific server

`claude mcp get github`

# Remove a server

`claude mcp remove github`

# (within Claude Code) Check server status

`/mcp`

# Add a local-scoped server (default)

`claude mcp add --transport http stripe https://mcp.stripe.com`

# Explicitly specify local scope

`claude mcp add --transport http stripe --scope local https://mcp.stripe.com`

# MCPs

_IMPORTANT_

After adding each MCP, authenticate using `claude /mcp`

## Figma

- Through Plugin

## Notion

`claude mcp add --transport http notion https://mcp.notion.com/mcp`

## Stripe

`claude mcp add --transport http stripe https://mcp.stripe.com/`

## Supabase

`claude mcp add --scope project --transport http supabase "https://mcp.supabase.com/mcp"`

## Vercel

`claude mcp add --transport http vercel https://mcp.vercel.com`

## Convex

```sh
claude mcp add-json convex '{"type":"stdio","command":"npx","args":["convex","mcp","start"]}'
claude mcp get convex
```

## Playwright

`claude mcp add playwright npx @playwright/mcp@latest`
