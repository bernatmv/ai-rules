# gamedev-core

Engine-agnostic game development skills for Claude Code. The transferable fundamentals that apply before you pick Three.js, Godot, or Unity — the game loop, design patterns, performance budgeting, and platform routing.

Pair with `gamedev-threejs`, `gamedev-godot`, or `gamedev-unity` for engine-specific implementation.

## Bundled skills

| Skill | Slash command | Focus |
| --- | --- | --- |
| `game-development` | `/gamedev-core:game-development` | Orchestrator — game loop, pattern/AI/collision selection, performance budget; routes to platform sub-skills (2D/3D, web, mobile, PC, VR/AR, design, art, audio, multiplayer) |
| `game-developer` | `/gamedev-core:game-developer` | Implementation patterns — ECS architecture, physics/colliders, multiplayer netcode with lag compensation, 60+ FPS optimization, shaders, object pooling, state machines |

The `game-development` orchestrator bundles ten sub-skill documents (`2d-games`, `3d-games`, `game-art`, `game-audio`, `game-design`, `mobile-games`, `multiplayer`, `pc-games`, `vr-ar`, `web-games`) that it routes to by relative path.

## Attribution

Vendored from these MIT-licensed community repos:

- `game-development` — [sickn33/agentic-awesome-skills](https://github.com/sickn33/agentic-awesome-skills) (`skills/game-development`), MIT.
- `game-developer` — [Jeffallan/claude-skills](https://github.com/Jeffallan/claude-skills) (`skills/game-developer`), MIT.

## Install

```sh
/plugin marketplace add bernatmv/ai-rules
/plugin install gamedev-core@ai-rules
/reload-plugins
```
