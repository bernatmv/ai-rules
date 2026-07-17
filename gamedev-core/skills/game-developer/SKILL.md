---
name: game-developer
description: "Engine-agnostic game systems guidance. Use when designing game architecture, applying ECS patterns, configuring physics and collision, setting up multiplayer networking with lag compensation, optimizing frame rates to 60+ FPS targets, or applying game design patterns such as object pooling and state machines. For engine-specific work, defer to the dedicated engine plugins (gamedev-unity, gamedev-threejs, gamedev-godot). Trigger keywords: game architecture, ECS architecture, game physics, multiplayer networking, game optimization, game AI, game design patterns."
license: MIT
metadata:
  author: https://github.com/Jeffallan
  version: "1.1.0"
  domain: specialized
  triggers: game architecture, ECS architecture, game physics, multiplayer networking, game optimization, game AI, game design patterns
  role: specialist
  scope: implementation
  output-format: code
  related-skills: 
---

# Game Developer

## Core Workflow

1. **Analyze requirements** — Identify genre, platforms, performance targets, multiplayer needs
2. **Design architecture** — Plan ECS/component systems, optimize for target platforms
3. **Implement** — Build core mechanics, graphics, physics, AI, networking
4. **Optimize** — Profile and optimize for 60+ FPS, minimize memory/battery usage
   - ✅ **Validation checkpoint:** Run the engine's profiler; verify frame time ≤16 ms (60 FPS) before proceeding. Identify and resolve CPU/GPU bottlenecks iteratively.
5. **Test** — Cross-platform testing, performance validation, multiplayer stress tests
   - ✅ **Validation checkpoint:** Confirm stable frame rate under stress load; run multiplayer latency/desync tests before shipping.

## Reference Guide

Load detailed guidance based on context:

| Topic | Reference | Load When |
|-------|-----------|-----------|
| ECS & Patterns | `references/ecs-patterns.md` | Entity Component System, game patterns |
| Performance | `references/performance-optimization.md` | FPS optimization, profiling, memory |
| Networking | `references/multiplayer-networking.md` | Multiplayer, client-server, lag compensation |

For engine-specific implementation (Unity, Three.js, Godot), use the dedicated engine plugin's skills instead.

## Constraints

### MUST DO
- Target 60+ FPS on all platforms
- Use object pooling for frequent instantiation
- Implement LOD systems for optimization
- Profile performance regularly (CPU, GPU, memory)
- Use async loading for resources
- Implement proper state machines for game logic
- Cache expensive lookups outside the per-frame loop
- Use delta time for frame-independent movement

### MUST NOT DO
- Instantiate/destroy objects in tight per-frame loops
- Skip profiling and performance testing
- Allocate memory inside the per-frame update loop
- Ignore platform-specific constraints (mobile, console)
- Run expensive scene/entity searches every frame
- Hardcode game values (use data assets/config files)

## Output Templates

When implementing game features, provide:
1. Core system implementation (component, system, or entity logic in the target engine's idiom)
2. Associated data structures (data assets, structs, configs)
3. Performance considerations and optimizations
4. Brief explanation of architecture decisions

[Documentation](https://jeffallan.github.io/claude-skills/skills/specialized/game-developer/)
