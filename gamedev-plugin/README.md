# gamedev-plugin

Three.js game and 3D development skills for Claude Code.

## Bundled skills

From [cloudai-x/threejs-skills](https://github.com/cloudai-x/threejs-skills) ([claudemarketplaces catalog](https://claudemarketplaces.com/skills/cloudai-x/threejs-skills)):

| Skill | Slash command | Focus |
| --- | --- | --- |
| `threejs-fundamentals` | `/gamedev-plugin:threejs-fundamentals` | Scene, camera, renderer, Object3D hierarchy |
| `threejs-geometry` | `/gamedev-plugin:threejs-geometry` | Built-in shapes, BufferGeometry, instancing |
| `threejs-materials` | `/gamedev-plugin:threejs-materials` | PBR, standard/phong materials, shaders |
| `threejs-lighting` | `/gamedev-plugin:threejs-lighting` | Light types, shadows, environment lighting |
| `threejs-textures` | `/gamedev-plugin:threejs-textures` | Texture types, UV mapping, render targets |
| `threejs-animation` | `/gamedev-plugin:threejs-animation` | Keyframe, skeletal, morph target animation |
| `threejs-loaders` | `/gamedev-plugin:threejs-loaders` | GLTF/GLB, async loading, caching |
| `threejs-shaders` | `/gamedev-plugin:threejs-shaders` | GLSL, ShaderMaterial, custom effects |
| `threejs-postprocessing` | `/gamedev-plugin:threejs-postprocessing` | EffectComposer, bloom, DOF, custom passes |
| `threejs-interaction` | `/gamedev-plugin:threejs-interaction` | Raycasting, controls, user input |
| `webgpu-threejs-tsl` | `/gamedev-plugin:webgpu-threejs-tsl` | WebGPU renderer, TSL node materials, compute shaders ([dgreenheck/webgpu-claude-skill](https://github.com/dgreenheck/webgpu-claude-skill)) |

### Game-building suite

From [majidmanzarpour/threejs-game-skills](https://github.com/majidmanzarpour/threejs-game-skills) — higher-level, end-to-end skills for shipping playable browser games. Start with `threejs-game-director`; it routes to the specialists below.

| Skill | Slash command | Focus |
| --- | --- | --- |
| `threejs-game-director` | `/gamedev-plugin:threejs-game-director` | Primary entrypoint — orchestrates full game builds, premium iteration, and phase routing |
| `threejs-gameplay-systems` | `/gamedev-plugin:threejs-gameplay-systems` | Playable slices, Vite/TS scaffold, game loop, entities, input, physics, scoring, game feel |
| `threejs-aaa-graphics-builder` | `/gamedev-plugin:threejs-aaa-graphics-builder` | Prototype→AAA visual upgrades, models, materials, lighting, VFX, render polish, visual scorecard |
| `threejs-game-ui-designer` | `/gamedev-plugin:threejs-game-ui-designer` | HUDs, menus, overlays, responsive layout, safe areas, touch UI, text fit |
| `threejs-debug-profiler` | `/gamedev-plugin:threejs-debug-profiler` | Black screens, runtime/loading/resize/mobile bugs, draw calls, triangles, memory, perf |
| `threejs-qa-release` | `/gamedev-plugin:threejs-qa-release` | Production builds, browser/mobile verification, canvas-pixel checks, release risk reports |
| `threejs-3d-generator` | `/gamedev-plugin:threejs-3d-generator` | Tripo API text/image→3D, game-ready GLB/FBX, rigging, animation, conversion (needs `TRIPO_API_KEY`) |
| `threejs-image-generator` | `/gamedev-plugin:threejs-image-generator` | Gemini concept art, textures, skies, decals, icons, logos, GUI/title art (needs `GEMINI_API_KEY`) |
| `threejs-audio-generator` | `/gamedev-plugin:threejs-audio-generator` | ElevenLabs SFX, ambience, UI sounds, voice/TTS, audio manifests (needs `ELEVENLABS_API_KEY`) |

The three asset generators are optional and only needed when generating external assets — the core game skills work without API keys. **Plugin caveat:** these generators and the director reference helper scripts via hardcoded `~/.claude/skills/<skill>/scripts/...` paths (they assume a global `npx skills add -g` install). When run as a bundled plugin those paths only resolve if the skills are also installed globally; otherwise invoke the scripts from this plugin's skill folders instead.

Complements `frontend-plugin` → `hyperframes` (`/hyperframes:three` for HyperFrames video contexts) — these skills target general Three.js game and interactive 3D development. `webgpu-threejs-tsl` complements `threejs-shaders` (WebGPU/TSL vs GLSL ShaderMaterial). The game-building suite layers on top of the low-level primitives above — primitives teach the API, the suite ships complete games.

See [`.claude/SKILLS.md`](../.claude/SKILLS.md).

## Install

```sh
/plugin marketplace add bernatmv/ai-rules
/plugin install gamedev-plugin@ai-rules
/reload-plugins
```
