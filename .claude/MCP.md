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

# MCPs by ai-rules plugin

External integrations are split across marketplace plugins. Install `fullstack-plugin@ai-rules` for core + frontend + devops MCPs in one step, or install plugins individually. See [PLUGIN.md](./PLUGIN.md).

## core-plugin

1. **Plugin dependencies (MCP)** — GitHub, GitLab, Notion, Stripe, Atlassian, Hugging Face, etc.
2. **`.mcp.json`** — MCPs without a matching official plugin:

| Server   | Transport | Notes                  |
| -------- | --------- | ---------------------- |
| `convex` | stdio     | `npx convex mcp start` |

3. **Google Workspace** — via `jean-claude` dependency (OAuth, not MCP). See [PLUGIN.md](./PLUGIN.md#google-workspace-gmail-drive-calendar).

## frontend-plugin

1. **Plugin dependencies (MCP)** — Figma, Playwright, Chrome DevTools
2. **`.mcp.json`**:

| Server       | Transport | Notes                      |
| ------------ | --------- | -------------------------- |
| `astro-docs` | http      | Astro documentation search |

## devops-plugin

**Plugin dependencies (MCP)** — Supabase, Vercel (no local `.mcp.json`).

---

After installing plugins, authenticate MCP servers with `/mcp`. Google Workspace uses
separate OAuth via `jean-claude` (see PLUGIN.md).

## gamedev-core

**`.mcp.json`**:

| Server    | Transport | Notes                                               |
| --------- | --------- | --------------------------------------------------- |
| `blender` | stdio     | `uvx mcp-for-blender` — needs `uv` + Blender add-on |

Community [MCP for Blender](https://github.com/ahujasid/blender-mcp) (renamed from `blender-mcp` in Sept 2026; the old name still works). Blender's side needs one-time setup: install [`uv`](https://docs.astral.sh/uv/), run `uvx mcp-for-blender install-addon`, restart Blender, enable **Interface: MCP for Blender** in **Edit → Preferences → Add-ons**, then in the 3D viewport press `N` → **MCP for Blender** tab → **Start MCP Server**. It connects on `localhost:9876` (override with `BLENDER_HOST` / `BLENDER_PORT`). Manual add:

```sh
claude mcp add blender -- uvx mcp-for-blender
```

## gamedev-roblox

**`.mcp.json`**:

| Server          | Transport | Notes                                       |
| --------------- | --------- | ------------------------------------------- |
| `roblox-studio` | stdio     | Binary shipped inside Roblox Studio         |

Roblox's standalone [studio-rust-mcp-server](https://github.com/Roblox/studio-rust-mcp-server) was archived in April 2026; this targets the [MCP server built into Studio](https://create.roblox.com/docs/studio/mcp). Enable it in Studio: **Assistant** → **…** → **Manage MCP Servers** → **Enable Studio as MCP server**. Manual add:

```sh
claude mcp add roblox-studio /Applications/RobloxStudio.app/Contents/MacOS/StudioMCP
```

Set `ROBLOX_STUDIO_MCP` to override the default macOS path (Windows: `%LOCALAPPDATA%\Roblox\mcp.bat`).

## Convex

Bundled in `core-plugin/.mcp.json`. Manual add:

```sh
claude mcp add-json convex '{"type":"stdio","command":"npx","args":["convex","mcp","start"]}'
claude mcp get convex
```

## Astro

Bundled in `frontend-plugin/.mcp.json`. Manual add:

```sh
claude mcp add --transport http "Astro docs" https://mcp.docs.astro.build/mcp
```

## Service MCPs (via plugin dependencies)

These are **not** duplicated in local `.mcp.json` files. Install the matching
ai-rules plugin or the individual official plugin:

| Service         | ai-rules plugin   | Official dependency                           |
| --------------- | ----------------- | --------------------------------------------- |
| Figma           | `frontend-plugin` | `figma@claude-plugins-official`               |
| Playwright      | `frontend-plugin` | `playwright@claude-plugins-official`          |
| Chrome DevTools | `frontend-plugin` | `chrome-devtools-mcp@claude-plugins-official` |
| Supabase        | `devops-plugin`   | `supabase@claude-plugins-official`            |
| Vercel          | `devops-plugin`   | `vercel@claude-plugins-official`              |
| Notion          | `core-plugin`     | `notion@claude-plugins-official`              |
| Stripe          | `core-plugin`     | `stripe@claude-plugins-official`              |
| GitHub          | `core-plugin`     | `github@claude-plugins-official`              |
| GitLab          | `core-plugin`     | `gitlab@claude-plugins-official`              |
| Atlassian       | `core-plugin`     | `atlassian@claude-plugins-official`           |
| Hugging Face    | `core-plugin`     | `huggingface-skills@claude-plugins-official`  |

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
