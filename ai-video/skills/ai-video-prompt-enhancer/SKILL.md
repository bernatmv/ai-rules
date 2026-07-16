---
name: ai-video-prompt-enhancer
description: Use when the user wants to generate a single AI video clip and needs to turn a rough idea into a detailed, cinematic prompt that modern AI video models can execute well. For multi-shot videos (TikTok Reels, Ads, Explainers), use ai-video-storyboard instead.
---

# AI Video Prompt Enhancer

## Overview

Most people write AI video prompts the same way they'd describe a scene to a friend: "a horse running in a field." Modern AI video models can technically render that, but the output looks generic because the prompt doesn't specify any of the things cinematographers actually care about — composition, camera movement, lighting, lens character, color grading, subject detail, or motion quality.

This skill turns a rough idea into a **production-grade cinematic prompt** that leverages the full vocabulary of filmmaking. Instead of "horse running in a field," you get something like:

> A majestic brown stallion galloping across a golden wheat field at sunset, cinematic wide tracking shot moving parallel to the horse, warm golden-hour backlight with visible lens flare, shallow depth of field at f/2.8, muted earth-tone color grade, 35mm anamorphic look with subtle film grain, slow motion 60fps feel, 8 seconds, 16:9, cinematic 1080p

The enhanced prompt specifies the visual language modern AI video models need to produce professional output. The difference in quality is usually the difference between "interesting AI clip" and "usable B-roll."

## When to Use

- User describes a video idea in one sentence and wants to generate a single clip
- User is frustrated with generic-looking AI video output
- User has a vague visual in mind but doesn't know cinematography vocabulary
- User wants to maximize quality on a limited credit budget (better prompt = fewer wasted generations)

**Do NOT use this skill for:**
- Multi-shot videos longer than ~15 seconds — use **ai-video-storyboard** instead, which plans a coordinated shot list
- Generating actual video (this skill only writes prompts; the user still needs an AI video tool)
- Image generation — different skill domain

## Workflow

### Step 1 — Capture the Core Idea

Ask the user **one combined question** (not a multi-turn interrogation):

> What scene do you want to generate? Tell me: **(1)** the subject, **(2)** what it's doing, **(3)** the mood or vibe, **(4)** the platform/aspect ratio (TikTok 9:16, YouTube 16:9, feed 1:1), and **(5)** the duration you're targeting (4s / 5s / 8s / 10s).

Accept whatever the user gives you, even partial answers. Fill in sensible defaults for missing fields:

| Missing field | Default |
|---|---|
| Duration | 5 seconds |
| Aspect ratio | 9:16 vertical |
| Mood | "cinematic" |

### Step 2 — Infer Visual Direction

Based on the subject + mood, decide on:

**Shot type.** Extreme close-up (ECU) for intimacy/detail, close-up (CU) for emotion, medium shot (MS) for action, medium wide (MWS) for subject-in-environment, wide shot (WS) for landscape/scale.

**Camera movement.** Locked-off for poise, slow dolly-in for building tension, tracking for parallel motion, crane-up for reveal, handheld for raw energy.

**Lighting.** Golden hour for warmth, overcast for mood, neon for urban/nightlife, rim light for drama, motivated window light for natural interiors, practical light sources for grounded realism.

**Lens character.** Shallow DOF for focus pulls and bokeh, deep focus for landscape/documentary, wide-angle for scale and mild distortion, telephoto for compressed backgrounds.

**Color grade.** Warm gold for nostalgia, cool teal for tech/modern, muted earth tones for documentary, high contrast for drama, desaturated for bleak mood.

**Film look.** Clean digital for contemporary, 16mm grain for analog warmth, 35mm anamorphic for cinematic scale, VHS/tape for retro.

**Motion quality.** Slow motion (60fps feel) for impact, normal speed for documentary, time-lapse for transitions.

### Step 3 — Write the Enhanced Prompt

Compose the prompt as a single paragraph, 40–80 words, following this structure:

```
[Shot type] [camera movement] of [detailed subject] [action] [environment],
[lighting description], [lens character and aperture], [color palette],
[film look], [technical style notes], [duration]s, [aspect ratio], cinematic 1080p
```

**Concrete over abstract.** Replace every generic noun with specific detail:

| Abstract | Concrete |
|---|---|
| "a woman" | "a woman in her late twenties with wavy auburn hair, wearing a denim jacket" |
| "a car" | "a vintage 1970 Ford Mustang in deep navy blue with chrome trim" |
| "a forest" | "an old-growth redwood forest with dense ferns and shafts of morning sunlight" |
| "a city" | "a rain-slicked Tokyo street in Shibuya, neon signs reflecting on the pavement" |
| "fast motion" | "slow-motion 60fps feel with motion blur on the limbs" |

**Always end with:** `[duration]s, [aspect ratio], cinematic 1080p`

### Step 4 — Show the Before/After

Present the user with:

1. **Their original idea** (one line, as they wrote it)
2. **The enhanced prompt** (ready to copy)
3. **A two-sentence explanation** of the key cinematographic choices you made and why

This teaches the user the vocabulary over time, and builds trust in the output. Without the explanation, enhanced prompts feel like black-box magic. With the explanation, users start writing better prompts themselves.

### Step 5 — Offer Variants (Optional)

If the user wants alternatives, generate 2–3 variants that change one axis at a time:

- **Mood variant** — same subject, different lighting/color (e.g., "golden hour" → "blue hour")
- **Scale variant** — same subject, different shot type (e.g., close-up → wide)
- **Motion variant** — same subject, different camera movement (e.g., locked-off → tracking)

This is how cinematographers explore coverage on a real set: same scene, multiple angles.

## Example

**User input:**
> "I want a video of a cat jumping off a kitchen counter"

**Enhanced prompt:**

> Slow-motion medium close-up of a sleek black-and-white tuxedo cat mid-jump from a white marble kitchen counter toward the floor, captured at 120fps slow-motion with subtle motion blur on the fur and paws, warm morning light streaming through a window on the left casting long shadows, shallow depth of field on the cat with blurred kitchen background, clean contemporary digital look with muted warm tones, 5 seconds, 9:16 vertical, cinematic 1080p

**Why these choices:**
Slow-motion was the obvious pick for a physical action shot — it turns a half-second real event into five seconds of visual content, and motion blur signals cinematic intent. Warm morning light grounds the scene in a specific time of day (which helps the model commit to consistent lighting), and the medium close-up shot keeps the cat as the subject while still showing enough environment to read as a kitchen.

## Critical Rules

1. **Always be concrete.** "A cat" is worthless. "A sleek black-and-white tuxedo cat mid-jump" gives the model something to commit to.
2. **Specify lighting explicitly.** "Good lighting" does nothing. "Warm morning light streaming through a window on the left" does.
3. **Always end with duration + aspect ratio + "cinematic 1080p".** This is the technical signal that most modern AI video models respond to.
4. **Don't use model-specific tricks.** Write prompts that work with any modern AI video model, not tricks tuned to one tool's quirks.
5. **Keep prompts to 40–80 words.** Longer prompts often confuse the model. Shorter prompts produce generic output.
6. **Explain your cinematography choices** to the user — don't just hand them a magic string.

## License

MIT — use freely, commercial or personal.
