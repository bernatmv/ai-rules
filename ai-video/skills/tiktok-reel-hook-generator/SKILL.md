---
name: tiktok-reel-hook-generator
description: Use when the user is making a TikTok, Instagram Reel, YouTube Short, or other short-form vertical video and needs a scroll-stopping 1-3 second visual hook. Generates multiple hook concepts with ready-to-copy AI video prompts for each, optimized for maximum watch-through in the critical first moments.
---

# TikTok / Reel Hook Generator

## Overview

The first **1.5 seconds** of a TikTok, Reel, or Short decide whether your video goes anywhere. Every platform's algorithm weights early watch-through more than any other signal — if viewers don't stop scrolling in the first 1–2 seconds, the rest of your video never gets shown to anyone.

This skill generates **visual hooks** optimized for that first critical moment: 1–3 second AI-video openings designed to make thumbs stop moving. It produces multiple hook concepts for the same topic, each with a ready-to-copy AI video prompt, so you can A/B test which opening lands best.

## When to Use

- User is making a short-form vertical video (TikTok, Reel, Short) and needs an attention-grabbing opening
- User has good content in the body of their video but the hook is weak and engagement is suffering
- User wants to A/B test multiple hook concepts for the same video topic
- User is batch-producing content and needs multiple hook variations per topic

**Do NOT use this skill for:**
- Long-form video (YouTube 10+ minute content) — hook rules are different
- Horizontal/landscape content — this skill is vertical-first (9:16)
- Full multi-shot videos — this skill generates the opening only; use **ai-video-storyboard** for full storyboards
- Generic prompt enhancement — use **ai-video-prompt-enhancer** for single-shot general-purpose prompts

## Workflow

### Step 1 — Understand the Video

Ask one combined question:

> What's the video about, and what's the payoff? Tell me: **(1)** the video topic (what the viewer will see overall), **(2)** the target audience, **(3)** the CTA or takeaway at the end, and **(4)** any brand/product you want to feature visually.

Accept partial answers. If the user only gives the topic, that's fine.

### Step 2 — Identify Which Hook Type Fits

There are six proven hook types for short-form vertical video. Pick the 2–3 that match the video's topic and vibe:

#### Hook Type 1: The Sensory Trigger

A close-up of something with strong texture, movement, or sensory appeal — food, liquids, fire, bubbles, fabric, ice, steam. Works because the brain is wired to pay attention to high-detail tactile content.

**Best for:** Food, cooking, lifestyle, ASMR-adjacent content, product unboxing

**Example hook prompt:**
> Extreme close-up overhead shot of thick golden honey slowly dripping from a wooden dipper onto a stack of fluffy pancakes, steam rising, warm natural morning light, shallow depth of field with blurred background, cinematic 1080p, 1.5 seconds, 9:16

#### Hook Type 2: The Disruption

An unexpected visual that breaks from scroll-feed norms — an object in the wrong place, scale mismatch, inverted colors, something starting mid-motion. Works because the brain stops to process unexpected patterns.

**Best for:** Surreal/creative content, brand storytelling, edgy marketing

**Example hook prompt:**
> A giant goldfish swimming through a busy city crosswalk at eye level as pedestrians walk around it unphased, overcast daylight, wide angle 24mm, slight motion blur, surreal cinematic look, cinematic 1080p, 2 seconds, 9:16

#### Hook Type 3: The Transformation Tease

Shows the "before" or "in-progress" state of something that will transform — a blank canvas, an empty room, a seed, a raw ingredient. Works because viewers stay to see the "after."

**Best for:** DIY, tutorials, before/after content, building/creating videos

**Example hook prompt:**
> Close-up of weathered hands slowly unwrapping a single vinyl record from worn brown paper on a wooden table, warm late afternoon window light, shallow depth of field, muted sepia color grade, cinematic 1080p, 2 seconds, 9:16

#### Hook Type 4: The Human Moment

A face — especially eyes, a subtle expression, or mid-reaction. Works because human faces hijack attention more reliably than any other visual stimulus.

**Best for:** Storytelling, testimonials, personal narratives, reaction content

**Example hook prompt:**
> Medium close-up of a woman in her late twenties slowly turning her head toward camera with a barely-there knowing smile, soft window light from the left creating gentle rim light on her hair, shallow depth of field with bokeh background, cinematic 1080p, 2 seconds, 9:16

#### Hook Type 5: The Motion Hook

Starts mid-motion — a runner already running, water already pouring, a car already in frame. Works because the brain can't finish processing incomplete motion, so it stays to see the resolution.

**Best for:** Sports, fitness, action content, product demos with movement

**Example hook prompt:**
> Low-angle tracking shot of a runner's feet mid-stride on wet pavement in slow motion, water droplets spraying up with each impact, golden hour rim light from behind, shallow depth of field, cinematic 1080p, 2 seconds, 9:16

#### Hook Type 6: The Scale Reveal

Starts tight and implies something much larger — a close-up of a part that will reveal to a whole, or a single element in a much bigger scene. Works because viewers stay to see the reveal.

**Best for:** Landscapes, architecture, epic/cinematic content, brand films

**Example hook prompt:**
> Extreme close-up of a single dewdrop on a blade of grass, perfectly still, reflecting a tiny inverted mountain in its surface, shallow depth of field, soft morning light, photorealistic detail, cinematic 1080p, 1.5 seconds, 9:16

### Step 3 — Generate 3 Hook Variants

Produce exactly **three** hook concepts for the user's video, each using a different hook type. This gives them A/B testing options without overwhelming them with choices.

For each hook, output:

```
## Hook Variant N: [Hook Type Name]

**Concept:** [One-sentence description of what the viewer sees]
**Why it works for this video:** [Why this hook type matches the video topic]

**Prompt to copy:**
> [Complete cinematic prompt, 40-70 words, ending with duration, 9:16, cinematic 1080p]

**Duration:** 1.5-3 seconds (use whichever fits the rhythm of your full video)
```

### Step 4 — Add Pacing Guidance

After the three hooks, add a short section:

```
## Pacing notes

- **Hook duration:** 1.5-2 seconds is the sweet spot. Shorter feels jumpy. Longer loses people.
- **First visible frame matters:** Your hook's opening frame is what people see in the scroll feed before any motion. Make sure frame 1 of the prompt makes sense as a still.
- **Sound hits at ~0.5s:** Whatever audio accompanies the hook (beat drop, snare, voice, whoosh) should hit 0.3-0.6 seconds after the visual starts. This is when the viewer's brain fully engages.
- **Cut to body content at the end of the hook:** The hook should feel like it's going somewhere, not like a complete thought. Leave a micro-cliffhanger.
```

### Step 5 — Offer Caption Overlay Suggestions (Optional)

If the user wants it, suggest 2–3 text overlay lines for the hook:

- **Question hooks:** "Wait... what is that?" / "How is this possible?"
- **Reveal hooks:** "You won't believe this" / "Watch until the end"
- **Direct hooks:** "POV: you finally" / "This one trick changed everything"

Caption overlays are platform-dependent — TikTok captions should be <8 words, bold sans-serif, bottom-center.

## Critical Rules

1. **Always produce exactly 3 hook variants.** More is decision fatigue; fewer is no A/B option.
2. **Use different hook types for each variant.** Don't generate three "sensory trigger" hooks — mix sensory, human, motion, disruption, etc.
3. **Match hook type to video topic.** Don't use a "human moment" hook for a landscape video. Don't use "sensory trigger" for a tech review.
4. **Every prompt ends with duration + 9:16 + cinematic 1080p.** Non-negotiable — this is the technical signal for vertical short-form.
5. **Hooks are 1.5–3 seconds max.** Longer isn't better. Shorter is fine.
6. **Frame 1 must work as a still.** Describe what's visible on the opening frame explicitly, so the model commits to a good thumbnail.

## License

MIT — use freely, commercial or personal.
