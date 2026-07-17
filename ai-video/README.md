# ai-video

AI video creation skills for Claude Code — plan, prompt, and hook short-form and cinematic AI video, plus the image and character-consistency skills that feed it.

## Bundled skills (6)

| Skill | Purpose | Source |
| ----- | ------- | ------ |
| `ai-video-storyboard` | Plan a multi-shot AI video (>15s) as a coordinated shot list with visually consistent per-segment prompts | [aicontentskills/ai-video-storyboard-skill](https://github.com/aicontentskills/ai-video-storyboard-skill) |
| `ai-video-prompt-enhancer` | Turn a rough idea into one detailed, cinematic single-clip prompt | [aicontentskills/ai-video-prompt-enhancer](https://github.com/aicontentskills/ai-video-prompt-enhancer) |
| `tiktok-reel-hook-generator` | Generate scroll-stopping 1–3s visual hooks with ready-to-copy prompts for TikTok / Reels / Shorts | [aicontentskills/tiktok-reel-hook-generator](https://github.com/aicontentskills/tiktok-reel-hook-generator) |
| `video-prompting` | Draft/refine model-specific prompts — Seedance 2.0, Kling, Ovi, Sora, Veo 3, Wan 2.2, LTX-2/2.3 | [Square-Zero-Labs/video-prompting-skill](https://github.com/Square-Zero-Labs/video-prompting-skill) (Apache-2.0); Kling reference from [smixs/visual-skills](https://github.com/smixs/visual-skills) (MIT) |
| `visual-image` | Image prompting for Nano Banana (NBP/NB2) and GPT Image 2 — covers storyboards, character sheets, product/UI shots | [smixs/visual-skills](https://github.com/smixs/visual-skills) (MIT, upstream `image`) |
| `character-design-sheet` | Character consistency across AI images — turnarounds, expression sheets, palettes, LoRA techniques | [inference-sh/skills](https://github.com/inference-sh/skills) (MIT) |

The `smixs/visual-skills` image skill is vendored under a clearer name (`visual-image`) to avoid the overly generic `image` slash command inside this plugin.

Use `/ai-video:ai-video-storyboard`, `/ai-video:ai-video-prompt-enhancer`, `/ai-video:tiktok-reel-hook-generator`, `/ai-video:video-prompting`, `/ai-video:visual-image`, or `/ai-video:character-design-sheet`.

### Rough → finished flow

- **Single clip:** `ai-video-prompt-enhancer` to shape the idea → `video-prompting` for the model-specific prompt.
- **Multi-shot / short-form:** `ai-video-storyboard` for the shot list → `tiktok-reel-hook-generator` for the opening hook → `video-prompting` per shot.
- **Character consistency first:** `character-design-sheet` or `visual-image` to lock a reference, then image-to-video prompting.

## Caveats

- `character-design-sheet` documents an inference.sh workflow and declares `allowed-tools: Bash(belt *)` — the runnable `belt app run …` examples require the `belt` CLI (`npx skills add belt-sh/cli`, then `belt login`). As a prompt/reference guide it works without it.
- The `aicontentskills/*` upstreams ship no `LICENSE` file; they are vendored as-is with attribution above. `smixs/visual-skills` is MIT, `Square-Zero-Labs/video-prompting-skill` is Apache-2.0, `inference-sh/skills` is MIT.

Complements `ai-tools-plugin` (HeyGen avatar/TTS/translation APIs), `frontend-plugin` video tooling (`hyperframes`, `remotion-plugin`), and `gamedev-threejs` asset generators.

## Install

```sh
/plugin marketplace add bernatmv/ai-rules
/plugin install ai-video@ai-rules
/reload-plugins
```

See [`.claude/SKILLS.md`](../.claude/SKILLS.md) for the skill → plugin mapping.
