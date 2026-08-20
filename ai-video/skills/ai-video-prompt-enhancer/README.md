# AI Video Prompt Enhancer

> A skill for Claude Code, Cursor, Windsurf, and other AI coding assistants that turns vague video ideas into production-grade cinematic prompts with specific lighting, camera, lens, and composition details. Works with any modern AI video generator.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Claude Code](https://img.shields.io/badge/Claude_Code-compatible-8B5CF6)](https://claude.com/claude-code)
[![Cursor](https://img.shields.io/badge/Cursor-compatible-000000)](https://cursor.com)

---

## The Problem

Most people write AI video prompts like this:

> "A horse running in a field"

And wonder why their outputs look generic. The issue isn't the model — it's the prompt. Cinematographers don't think in "horse running in a field." They think in shot type, camera movement, lighting direction, lens character, color palette, film stock, and motion quality. Those are the levers that separate "interesting AI clip" from "usable professional footage."

This skill bridges the gap. Give it a rough idea, get back a production-grade cinematic prompt that modern AI video models can actually execute well.

## Before and After

**You:**
> "A cat jumping off a kitchen counter"

**The skill outputs:**

> Slow-motion medium close-up of a sleek black-and-white tuxedo cat mid-jump from a white marble kitchen counter toward the floor, captured at 120fps slow-motion with subtle motion blur on the fur and paws, warm morning light streaming through a window on the left casting long shadows, shallow depth of field on the cat with blurred kitchen background, clean contemporary digital look with muted warm tones, 5 seconds, 9:16 vertical, cinematic 1080p

Plus a short explanation of the cinematography choices, so you learn the vocabulary over time instead of relying on the skill forever.

## What's Different About This Skill

Unlike generic "prompt optimizers" that just add fluff words to your input, this skill:

1. **Asks for specifics up front** — subject, action, mood, platform, duration — in a single question, not a multi-turn interrogation
2. **Makes cinematography decisions explicitly** — shot type, camera move, lighting, lens, color, film look, motion
3. **Turns abstract nouns into concrete detail** — "a woman" becomes "a woman in her late twenties with wavy auburn hair, wearing a denim jacket"
4. **Explains the choices** — you see WHY the prompt works, not just what it says
5. **Offers variants on request** — mood, scale, and motion variants for exploring coverage

## When to Use This Skill

- ✅ Generating a **single** AI video clip and want it to look professional
- ✅ You have a rough idea but don't know cinematography vocabulary
- ✅ Your AI video outputs keep looking generic and you don't know why
- ✅ You want to get more quality out of limited generation credits

## When NOT to Use This Skill

- ❌ **Multi-shot videos longer than ~15 seconds** — use [ai-video-storyboard](https://github.com/aicontentskills/ai-video-storyboard-skill) instead for coordinated shot lists with visual consistency across shots
- ❌ Image generation — wrong domain
- ❌ You just want to run an AI video model — this skill writes prompts, not videos

## Installation

### Claude Code

```bash
# User-level (all projects)
mkdir -p ~/.claude/skills/ai-video-prompt-enhancer
cp SKILL.md ~/.claude/skills/ai-video-prompt-enhancer/SKILL.md
```

Invoke in any Claude Code session:

```
Use the ai-video-prompt-enhancer skill to turn this into a cinematic prompt:
a cat jumping off a kitchen counter
```

### Cursor / Windsurf

Copy the contents of `SKILL.md` (without frontmatter) into your project's `.cursorrules` or `.windsurfrules` file.

### ChatGPT / Claude.ai

Paste `SKILL.md` as system instructions for a custom GPT or project.

## Compatible With

Works with any modern AI video generator — it writes model-agnostic cinematic prompts, not platform-specific tricks.

## Part of AI Content Skills

This skill is part of the [**AI Content Skills**](https://github.com/aicontentskills) collection — open-source skills for AI creators. Companion skill: [**ai-video-storyboard**](https://github.com/aicontentskills/ai-video-storyboard-skill) for multi-shot video planning.

## License

MIT — use freely, commercial or personal.
