# gamedev-godot

Godot 4.x game development skills plus the `godot-mcp` server for Claude Code.

Pair with `gamedev-core` for engine-agnostic fundamentals.

## Bundled skill

| Skill | Slash command | Focus |
| --- | --- | --- |
| `godot` | `/gamedev-godot:godot` | Develop, test, build, and deploy Godot 4.x games — GDScript, GdUnit4 unit testing, PlayGodot automation, web/desktop exports, CI/CD pipelines, deployment to Vercel/GitHub Pages/itch.io |

Also provides the `/gamedev-godot:godot` slash command and Python helper scripts (`run_tests.py`, `parse_results.py`, `export_build.py`, `validate_project.py`) under `skills/godot/scripts/`.

## godot-mcp server

`.mcp.json` wires up [godot-mcp](https://github.com/Coding-Solo/godot-mcp) — launch the editor, run projects, capture debug output, and manage scenes from chat. It runs via `npx @coding-solo/godot-mcp` and needs Godot on your machine:

```sh
export GODOT_PATH=/path/to/godot        # absolute path to the Godot 4.x executable
```

The MCP config references `${GODOT_PATH}`; set it in your environment before starting Claude Code. If unset, the server attempts to auto-detect Godot.

## Attribution

Vendored from these MIT-licensed repos:

- `godot` skill + `/godot` command — [Randroids-Dojo/skills](https://github.com/Randroids-Dojo/skills) (`plugins/godot`), MIT.
- `godot-mcp` server — [Coding-Solo/godot-mcp](https://github.com/Coding-Solo/godot-mcp), MIT (installed on demand via npx).

## Install

```sh
/plugin marketplace add bernatmv/ai-rules
/plugin install gamedev-godot@ai-rules
/reload-plugins
```
