# gamedev-unity

Unity game development for Claude Code — the **agent-facing skill docs** for automating the Unity Editor. Pair with `gamedev-core` for engine-agnostic fundamentals.

> **Important:** Unlike `gamedev-godot`, Unity automation cannot be driven from a self-contained npx MCP server. Both Unity integrations run **inside the Unity Editor** and must be installed on the Unity side. This plugin ships the docs the agent uses once that setup is in place; it does not install or launch anything in Unity for you.

## Bundled skill

| Skill | Slash command | Focus |
| --- | --- | --- |
| `unity-skills` | `/gamedev-unity:unity-skills` | Automate the Unity Editor through the local UnitySkills REST server — create/edit scripts, build scenes and prefabs, manage assets/materials/lighting, run tests, and drive hundreds of Editor operations across ~70 module docs |

The skill routes through a local REST bridge and a Python helper (`skills/unity-skills/scripts/unity_skills.py`). It only functions when the Unity Editor plugin below is installed and its server is running.

## Unity-side setup (required)

Pick one (or both) of these MIT-licensed integrations and install them in your Unity project:

### 1. UnitySkills (the REST bridge these docs describe)

The bundled `unity-skills` docs target this server. Install the [Besty0728/Unity-Skills](https://github.com/Besty0728/Unity-Skills) UPM package (Unity 2022.3+), open `Window > UnitySkills`, and start the server. Operating mode (approval / auto / bypass) is a server-side permission gate configured in that panel.

### 2. unity-mcp (Model Context Protocol)

Alternatively, [CoplayDev/unity-mcp](https://github.com/CoplayDev/unity-mcp) exposes Unity to any MCP client. Install via Unity Package Manager (git URL `https://github.com/CoplayDev/unity-mcp.git?path=/MCPForUnity#main`, or `openupm add com.coplaydev.unity-mcp`), needs Unity 2021.3–6.x + Python 3.10+ via `uv`. Configure clients from **`Window → MCP for Unity → Configure All Detected Clients`** — the Unity editor writes the MCP server config for detected clients itself, so no `.mcp.json` is shipped here.

## Attribution

Vendored from these MIT-licensed repos:

- `unity-skills` docs — [Besty0728/Unity-Skills](https://github.com/Besty0728/Unity-Skills) (`SkillsForUnity/unity-skills~`), MIT. The bundled CJK font in the upstream UPM package (not vendored here) uses SIL OFL 1.1.
- `unity-mcp` — [CoplayDev/unity-mcp](https://github.com/CoplayDev/unity-mcp), MIT.

## Install

```sh
/plugin marketplace add bernatmv/ai-rules
/plugin install gamedev-unity@ai-rules
/reload-plugins
```
