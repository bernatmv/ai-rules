# roblox-gamedev

Roblox game development: 44 skills and 7 worker agents, from a one-line game idea to a playtested build and trailer. Start with `/roblox-gamedev:roblox-skills-setup`, then `/roblox-gamedev:create-roblox-game`.

## Setup

The plugin ships no MCP config, because the skills expect the server names below and plugin-registered servers get a prefixed name.

```sh
claude mcp add --scope user Roblox_Studio /Applications/RobloxStudio.app/Contents/MacOS/StudioMCP
claude mcp add --scope user blender -- uvx mcp-for-blender
```

Enable the Studio server under **Assistant** → **…** → **Manage MCP Servers** → **Enable Studio as MCP server**. Keep one Studio connection at a time. Blender needs its add-on as well; see [`.claude/MCP.md`](../.claude/MCP.md).

Run `roblox-skills-setup` to check local tools (Rojo, Wally, Lune, Selene, StyLua, Blender, Python 3.11+). Per-skill settings live in `~/.config/roblox-gamedev/<skill>/LOCAL.md`, outside the plugin, so updates keep them.

## Skills

| Group | Skills | Source |
| --- | --- | --- |
| Game pipeline | `create-roblox-game`, `roblox-build-orchestrator`, `roblox-skills-setup` | SyphoDev |
| Build | `roblox-code`, `roblox-ui`, `roblox-map`, `roblox-3d-model`, `roblox-texture-gen`, `roblox-vfx`, `roblox-sfx`, `roblox-animation` | SyphoDev |
| Economy | `roblox-economy` | mvvthw |
| Style and marketing | `studify`, `roblox-trailer` | zriptic |
| Blender | 30 skills; `text-to-blender` is the entry point | RobLe3 |

The worker agents (`roblox-asset-*`, `roblox-market-scout`) load automatically as `roblox-gamedev:<name>`.

Upstream warns against the Kaggle route in `roblox-3d-model` and `roblox-ui`: Kaggle's terms ban this use. Its scripts are vendored unchanged, so don't run the `kaggle_*` files.

## Sources and licenses

| Upstream | Commit | License |
| --- | --- | --- |
| [SyphoDev-yt/roblox-ai-skills](https://github.com/SyphoDev-yt/roblox-ai-skills), from the [SyphoDev YouTube channel](https://www.youtube.com/@SyphoDev) | `5aad881` | [Free licence](licenses/SyphoDev-roblox-ai-skills.txt): free sharing with this link back, no selling or paid bundles |
| [mvvthw/roblox-claude-skills](https://github.com/mvvthw/roblox-claude-skills) (`roblox-economy`) | `693a06d` | [MIT](licenses/mvvthw-roblox-claude-skills.txt) |
| [zriptic/roclicks-skills](https://github.com/zriptic/roclicks-skills) (`roblox-trailer`, `studify`) | `a8b66c1` | MIT, in each skill folder |
| [RobLe3/cc-blender-skill](https://github.com/RobLe3/cc-blender-skill) | `a2634b5` | [MIT](licenses/RobLe3-cc-blender-skill.txt) |

## Local adaptations

Re-apply these after refreshing from upstream:

- Hardcoded `~/.claude/skills/<name>` paths became `${CLAUDE_PLUGIN_ROOT}/skills/<name>` in `SKILL.md`, `<plugin-root>/skills/<name>` in reference files and generated comments, and script-relative paths in Python output.
- `LOCAL.md` moved to `~/.config/roblox-gamedev/<skill>/`, because the plugin cache is replaced on update.
- `roblox-build-orchestrator` uses the plugin's `agents/` directly, and its duplicate `agents/` copy was removed.
- The `roblox-code` scaffold's test runner uses a file-relative require and pins Lune 0.10.5, because newer Lune rejects the upstream path.
- `calibrate_rig.py`, `anim_render.py` and `r6_clip.py` in `roblox-animation` also run on Blender 5, which removed `Action.fcurves` and renamed the EEVEE engine.
- `manifest.json` comes from cc-blender-skill and is read by `blender-skill-harmonizer`.
