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

Complements `frontend-plugin` → `hyperframes` (`/hyperframes:three` for HyperFrames video contexts) — these skills target general Three.js game and interactive 3D development. `webgpu-threejs-tsl` complements `threejs-shaders` (WebGPU/TSL vs GLSL ShaderMaterial).

See [`.claude/SKILLS.md`](../.claude/SKILLS.md).

## Install

```sh
/plugin marketplace add bernatmv/ai-rules
/plugin install gamedev-plugin@ai-rules
/reload-plugins
```
