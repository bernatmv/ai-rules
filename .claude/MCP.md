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

# MCPs in core-plugin

`core-plugin@ai-rules` bundles external integrations three ways:

1. **Plugin dependencies (MCP)** — Notion, Stripe, Supabase, Vercel, Playwright, Figma,
   GitHub, GitLab, Atlassian, Chrome DevTools, Hugging Face, etc. See [PLUGIN.md](./PLUGIN.md).
2. **`.mcp.json` in core-plugin (MCP)** — integrations without a matching plugin:
3. **Google Workspace (Gmail, Drive, Calendar)** — via the `jean-claude` plugin dependency
   (skill/CLI + OAuth, not MCP). See [PLUGIN.md](./PLUGIN.md#google-workspace-gmail-drive-calendar).

| Server       | Transport | Notes                      |
| ------------ | --------- | -------------------------- |
| `convex`     | stdio     | `npx convex mcp start`     |
| `astro-docs` | http      | Astro documentation search |

After installing core-plugin, authenticate MCP servers with `/mcp`. Google Workspace uses
separate OAuth via `jean-claude` (see PLUGIN.md).

## Convex

Bundled in `core-plugin/.mcp.json`. Manual add:

```sh
claude mcp add-json convex '{"type":"stdio","command":"npx","args":["convex","mcp","start"]}'
claude mcp get convex
```

## Astro

Bundled in `core-plugin/.mcp.json`. Manual add:

```sh
claude mcp add --transport http "Astro docs" https://mcp.docs.astro.build/mcp
```

## Service MCPs (via plugin dependencies)

These are **not** duplicated in `core-plugin/.mcp.json`. Install `core-plugin@ai-rules`
or the individual plugin from `claude-plugins-official`:

| Service         | Plugin dependency                             |
| --------------- | --------------------------------------------- |
| Figma           | `figma@claude-plugins-official`               |
| Notion          | `notion@claude-plugins-official`              |
| Stripe          | `stripe@claude-plugins-official`              |
| Supabase        | `supabase@claude-plugins-official`            |
| Vercel          | `vercel@claude-plugins-official`              |
| Playwright      | `playwright@claude-plugins-official`          |
| GitHub          | `github@claude-plugins-official`              |
| GitLab          | `gitlab@claude-plugins-official`              |
| Atlassian       | `atlassian@claude-plugins-official`           |
| Chrome DevTools | `chrome-devtools-mcp@claude-plugins-official` |
| Hugging Face    | `huggingface-skills@claude-plugins-official`  |

## Google Workspace (Gmail, Drive, Calendar)

There is no official Google MCP in `claude-plugins-official`. `core-plugin` depends on
`jean-claude@jean-claude` instead — a skill/CLI plugin with OAuth, not an MCP server.

After install, authenticate once:

```
Set up Google authentication for jean-claude
```

Requires [uv](https://docs.astral.sh/uv/). Credentials: `~/.config/jean-claude/token.json`.

Manual MCP add (without plugins):

```sh
claude mcp add --transport http notion https://mcp.notion.com/mcp
claude mcp add --transport http stripe https://mcp.stripe.com/
claude mcp add --scope project --transport http supabase "https://mcp.supabase.com/mcp"
claude mcp add --transport http vercel https://mcp.vercel.com
claude mcp add playwright npx @playwright/mcp@latest
```

## Add a local-scoped server (default)

```sh
claude mcp add --transport http stripe https://mcp.stripe.com
```

## Explicitly specify local scope

```sh
claude mcp add --transport http stripe --scope local https://mcp.stripe.com
```
