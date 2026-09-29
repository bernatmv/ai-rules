# gamedev-core

Engine-agnostic game development skills for Claude Code. The transferable fundamentals that apply before you pick Three.js or Godot — architecture, design patterns, performance budgeting, and per-platform guidance.

Pair with `gamedev-threejs`, `gamedev-godot`, or `gamedev-roblox` for engine-specific implementation.

## Bundled skills

| Skill | Slash command | Focus |
| --- | --- | --- |
| `game-developer` | `/gamedev-core:game-developer` | Implementation patterns — ECS architecture, physics/colliders, multiplayer netcode with lag compensation, 60+ FPS optimization, shaders, object pooling, state machines |
| `2d-games`, `3d-games` | `/gamedev-core:2d-games`, … | Sprites and tilemaps; meshes and shaders |
| `web-games`, `mobile-games`, `pc-games`, `vr-ar` | `/gamedev-core:web-games`, … | Per-platform framework choice, input, and distribution |
| `game-design`, `game-art`, `game-audio`, `multiplayer` | `/gamedev-core:game-design`, … | GDD and balancing; asset pipeline; sound design; netcode |

The upstream `game-development` orchestrator was dropped — it duplicated `game-developer` (game loop, pattern/AI/collision selection, performance budget), and the ten platform documents it routed to are now top-level skills the agent selects directly.

## MCP server

`.mcp.json` wires up [MCP for Blender](https://github.com/ahujasid/blender-mcp) (`uvx mcp-for-blender`) for modeling, scene editing, and asset work from chat.

Blender's side needs one-time setup: install [`uv`](https://docs.astral.sh/uv/), run `uvx mcp-for-blender install-addon`, restart Blender, enable **Interface: MCP for Blender** in **Edit → Preferences → Add-ons**, then in the 3D viewport press `N` → **MCP for Blender** tab → **Start MCP Server**. It connects on `localhost:9876` (override with `BLENDER_HOST` / `BLENDER_PORT`).

> The server runs LLM-generated Python inside Blender with no sandbox by default. Set `BLENDER_MCP_SAFE_MODE=1` to block file, subprocess, and network access (this also blocks exporting to disk).

This is the community server, not the official [Blender Lab MCP server](https://www.blender.org/lab/mcp-server/) (Blender 5.1+, GPL, no asset libraries or 3D generation, distributed as an `.mcpb` bundle rather than a package).

## Attribution

Vendored from these MIT-licensed community repos:

- Platform skills (`2d-games`, `3d-games`, `game-art`, `game-audio`, `game-design`, `mobile-games`, `multiplayer`, `pc-games`, `vr-ar`, `web-games`) — [sickn33/agentic-awesome-skills](https://github.com/sickn33/agentic-awesome-skills) (`skills/game-development`), MIT.
- `game-developer` — [Jeffallan/claude-skills](https://github.com/Jeffallan/claude-skills) (`skills/game-developer`), MIT.

## Install

```sh
/plugin marketplace add bernatmv/ai-rules
/plugin install gamedev-core@ai-rules
/reload-plugins
```
