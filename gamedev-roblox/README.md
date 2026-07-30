# gamedev-roblox

Roblox game development via the MCP server **built into Roblox Studio**.

Pair with `gamedev-core` for engine-agnostic fundamentals.

## Which Roblox MCP is this?

Roblox shipped a standalone MCP server, [Roblox/studio-rust-mcp-server](https://github.com/Roblox/studio-rust-mcp-server), which was **archived in April 2026**. Its README now points to the [MCP server built into Roblox Studio](https://create.roblox.com/docs/studio/mcp) as the supported path forward. This plugin wires up the built-in server — don't install the archived standalone binary alongside it.

## Studio-side setup (required)

Like `gamedev-unity`, this needs setup inside the editor. The server is a binary shipped with Studio, and it only answers once Studio is running with MCP enabled:

1. Open Roblox Studio.
2. Open the **Assistant** panel → menu (**…**) → **Manage MCP Servers**.
3. Enable **Enable Studio as MCP server**.
4. Restart Claude Code. Studio's MCP settings show a green indicator once connected.

Studio's Assistant settings also offer a **Quick connect** dropdown with a Claude Code toggle, which writes the client config for you. Use either that or this plugin — not both, or you get two entries for the same server.

## Server path

`.mcp.json` defaults to the macOS Studio location:

```
/Applications/RobloxStudio.app/Contents/MacOS/StudioMCP
```

Override it for other platforms or a non-default install:

```sh
export ROBLOX_STUDIO_MCP="$LOCALAPPDATA\\Roblox\\mcp.bat"   # Windows
```

The config reads `${ROBLOX_STUDIO_MCP}` and falls back to the macOS path when unset.

## Tools

Provided by Studio, grouped as the [docs](https://create.roblox.com/docs/studio/mcp) list them:

| Group | Tools |
| --- | --- |
| Scripts | `script_read`, `multi_edit`, `script_search`, `script_grep` |
| Content generation | `generate_mesh`, `generate_material`, `generate_procedural_model`, `insert_asset`, `upload_image` |
| Data model | `search_game_tree`, `inspect_instance` |
| Execution | `execute_luau` |
| Playtesting | `start_stop_play`, `screen_capture`, `character_navigation`, `user_keyboard_input`, `user_mouse_input` |
| Documentation | `http_get`, `skill` |

Tool availability tracks your Studio version, so a client connected to an older Studio sees fewer of them.

> **Note:** an MCP client connected to Studio can read and modify the contents of your open place. Only connect tools you trust, and be deliberate about which place is open.

## Install

```sh
/plugin marketplace add bernatmv/ai-rules
/plugin install gamedev-roblox@ai-rules
/reload-plugins
```
