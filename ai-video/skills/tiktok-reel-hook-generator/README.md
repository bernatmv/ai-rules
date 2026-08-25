# TikTok / Reel Hook Generator

> A skill for Claude Code, Cursor, Windsurf, and other AI coding assistants that generates scroll-stopping visual hooks for TikTok, Instagram Reels, and YouTube Shorts. Produces 3 hook variants per topic with ready-to-copy AI video prompts, optimized for maximum watch-through in the critical first 1.5 seconds.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Claude Code](https://img.shields.io/badge/Claude_Code-compatible-8B5CF6)](https://claude.com/claude-code)
[![Cursor](https://img.shields.io/badge/Cursor-compatible-000000)](https://cursor.com)

---

## The Problem

The first **1.5 seconds** of a TikTok / Reel / Short decide whether anyone sees the rest of your video. Every short-form platform weighs early watch-through more than any other signal: if viewers don't stop scrolling in those first 1–2 seconds, your video dies in the feed.

Most creators focus on the body of their video and treat the hook as an afterthought. That's backwards. **The hook is the video.** If the hook works, the body gets seen. If the hook fails, nothing else matters.

This skill generates scroll-stopping visual hooks as AI video prompts, using six proven hook patterns (sensory trigger, disruption, transformation tease, human moment, motion hook, scale reveal) — each with specific cinematographic choices that make viewers' thumbs stop.

## What It Does

Give it a video topic. The skill returns:

1. **Three distinct hook variants** using different hook patterns — so you can A/B test which opening lands best
2. **Ready-to-copy AI video prompts** for each hook, 40–70 words, optimized for 9:16 vertical 1080p output
3. **A "why it works" explanation** for each hook so you learn the patterns
4. **Pacing notes** — hook duration, opening frame requirements, audio timing cues
5. **Optional caption overlay suggestions** for the hook text

## The Six Hook Patterns

| # | Pattern | Best For | Why It Works |
|---|---|---|---|
| 1 | **Sensory Trigger** | Food, lifestyle, ASMR | Brain hardwired for tactile detail |
| 2 | **Disruption** | Brand, surreal, creative | Unexpected patterns force processing |
| 3 | **Transformation Tease** | DIY, tutorials, build-up | Viewers stay for the "after" |
| 4 | **Human Moment** | Storytelling, testimonial, personal | Faces hijack attention |
| 5 | **Motion Hook** | Sports, action, product demos | Incomplete motion demands resolution |
| 6 | **Scale Reveal** | Landscape, epic, cinematic | Viewers stay for the reveal |

The skill automatically picks the 2–3 patterns that fit your video topic, so you don't need to memorize them.

## Example

**You:**
> "Video about my bakery's new sourdough loaf. Warm handcrafted vibe. CTA is visit us this weekend."

**The skill generates 3 hook variants:**

### Hook Variant 1: Sensory Trigger

**Concept:** Close-up of hands tearing open a fresh sourdough loaf, steam rising from the crust.

**Prompt to copy:**
> Extreme close-up overhead shot of weathered baker's hands tearing open a freshly baked rustic sourdough loaf, steam rising from the golden-brown crust, flour dust visible in warm window light, rich caramelized texture on the crust, shallow depth of field with blurred flour-dusted wooden counter, subtle 16mm film grain, 2 seconds, 9:16, cinematic 1080p

### Hook Variant 2: Transformation Tease

**Concept:** Close-up of raw dough being placed in a cast-iron dutch oven — implies the transformation to finished loaf.

**Prompt to copy:**
> ...

### Hook Variant 3: Sensory Trigger (Motion)

**Concept:** Butter melting on a warm slice of sourdough.

**Prompt to copy:**
> ...

Plus pacing notes and optional caption overlays.

## When to Use This Skill

- ✅ Making TikToks, Instagram Reels, or YouTube Shorts and want the opening to actually land
- ✅ A/B testing hook concepts for the same video topic
- ✅ Batch-producing content — you need multiple hook ideas per topic fast
- ✅ Your body content is good but your watch-through rates are low

## When NOT to Use This Skill

- ❌ **Long-form YouTube** (10+ minutes) — hook rules are different
- ❌ **Horizontal/landscape** content — this skill is 9:16 vertical only
- ❌ **Full video planning** — use [ai-video-storyboard](https://github.com/aicontentskills/ai-video-storyboard-skill) for multi-shot storyboards
- ❌ **Generic single-shot prompts** — use [ai-video-prompt-enhancer](https://github.com/aicontentskills/ai-video-prompt-enhancer) for non-hook prompts

## Installation

### Claude Code

```bash
mkdir -p ~/.claude/skills/tiktok-reel-hook-generator
cp SKILL.md ~/.claude/skills/tiktok-reel-hook-generator/SKILL.md
```

### Cursor / Windsurf

Copy `SKILL.md` contents (without frontmatter) into your `.cursorrules` or `.windsurfrules` file.

### ChatGPT / Claude.ai

Paste `SKILL.md` as system instructions for a custom GPT or project.

## Compatible With

Works with any modern AI video generator that produces 9:16 vertical 1080p output.

## Part of AI Content Skills

This skill is part of the [**AI Content Skills**](https://github.com/aicontentskills) collection — open-source skills for AI creators. Companion skills:

- [**ai-video-storyboard**](https://github.com/aicontentskills/ai-video-storyboard-skill) — plans full multi-shot videos with visual consistency
- [**ai-video-prompt-enhancer**](https://github.com/aicontentskills/ai-video-prompt-enhancer) — turns rough video ideas into cinematic single-shot prompts

## License

MIT — use freely, commercial or personal.
