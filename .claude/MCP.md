# Found at

```sh
~/.claude.json
```

# List all configured servers

```sh
claude mcp list
```

# Get details for a specific server

```sh
claude mcp get github
```

# Remove a server

```sh
claude mcp remove github
```

# (within Claude Code) Check server status

```sh
/mcp
```

# Add a local-scoped server (default)

```sh
claude mcp add --transport http stripe https://mcp.stripe.com
```

# Explicitly specify local scope

```sh
claude mcp add --transport http stripe --scope local https://mcp.stripe.com
```

# MCPs

_IMPORTANT_

After adding each MCP, authenticate using

```sh
/mcp
```

## Figma

- Through Plugin

## Notion

```sh
claude mcp add --transport http notion https://mcp.notion.com/mcp
```

## Stripe

```sh
claude mcp add --transport http stripe https://mcp.stripe.com/
```

## Supabase

```sh
claude mcp add --scope project --transport http supabase "https://mcp.supabase.com/mcp"
```

## Vercel

```sh
claude mcp add --transport http vercel https://mcp.vercel.com
```

## Convex

```sh
claude mcp add-json convex '{"type":"stdio","command":"npx","args":["convex","mcp","start"]}'
claude mcp get convex
```

## Playwright

```sh
claude mcp add playwright npx @playwright/mcp@latest
```

## Astro

```sh
claude mcp add --transport http "Astro docs" https://mcp.docs.astro.build/mcp
```
