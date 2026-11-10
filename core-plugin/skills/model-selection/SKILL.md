---
name: model-selection
description: >
  Starting points for choosing a Claude model and effort level (Haiku, Sonnet,
  Opus, Fable), or a Codex model, by task. Use when picking a model or effort,
  when a model falls short or costs too much, when spawning or defining
  subagents, or when choosing a model for an LLM feature. Guidance, not policy:
  an explicit choice from the user or project wins.
---

# Model selection

These are starting points, not rules. An explicit choice from the user, the project, or another skill wins, and so does evidence from the task in front of you. Don't interrupt a small task to change models.

Use aliases (`opus`, `sonnet`, `haiku`, `fable`) rather than dated IDs, so choices keep working as models ship. Switch with `/model <alias>` and `/effort <level>`; `/effort status` shows the current level.

## Where to start

When unsure, use **Opus at `medium`**.

| Work | Model | Effort |
| --- | --- | --- |
| Everyday engineering, debugging, multi-PR features | Opus | `medium`, then `high` |
| Well-scoped coding: bug fixes, iteration, building to a spec | Sonnet | `medium`, then `high` |
| Chat and interactive sessions | Sonnet | `low` or `medium` |
| Everyday documents, slides, spreadsheets | Sonnet | `medium` to `high` |
| Repeated agent tasks: investigation, review, drafting | Sonnet | `medium` |
| Computer use and vision-heavy loops | Opus | `medium` |
| Complex financial models, documents from large source sets | Opus | `medium` |
| Classification, routing, tagging, high-volume extraction | Haiku | default |
| Subagents that search files, read logs, summarize | Haiku or Sonnet | default |
| Major refactors and migrations, architecture, leading many subagents | Fable | `medium`, then `high` |
| Deep research, scientific or quantitative analysis | Fable | `medium`, then `high` |
| Long unattended runs on hard problems | Fable | `medium`, then `high` |

A clear spec doesn't by itself mean Sonnet. A migration or performance optimization can still need Opus or Fable.

## When the result falls short

Work down this list in order:

1. Make sure the model can check its own work with a test, a build, or a script that exercises the behavior. This is often cheaper than more effort.
2. Raise effort one level.
3. Move up a model, starting at a lower effort than you used on the smaller one.

Effort buys longer thinking, more tool calls, and more self-checking, at the price of latency. It doesn't add knowledge or skill, which is when to move up a model. Past `high`, one more level can cost as much as the next model, so compare the next model at lower effort before going further.

When outcomes can be checked automatically, consider running at `low` and re-running only the failures at `high`.

If a task runs well below these starting points, move down. Cost per finished task matters more than token price, and the hardest tasks carry most of the spend.

## Subagents

- Give smaller models work where a wrong answer is cheap to spot: finding files, running tests, reading logs.
- Keep code edits and judgment on the main model.
- Set `model: haiku` or `model: sonnet` in the subagent definition. `CLAUDE_CODE_SUBAGENT_MODEL` sets the default for subagents with none.
- Built-in Explore runs on the session's model, so define your own `Explore` with `model: haiku` if exploration should be cheap.
- Let cheap subagents read verbose material so the expensive model's context stays lean.

## Switching mid-session

The prompt cache belongs to the model that wrote it, so the first turn on a new model pays to rewrite it. Switch at a natural break: run `/compact` first, or start fresh from a short written plan. Moving down a tier can also lose earlier reasoning.

## Codex

The source article covers Claude only. The same reasoning applies: start from the cheaper capable model, try effort before changing model, and move up on evidence.

- **Luna** (`gpt-5.6-luna`) for routine and well-scoped coding.
- **Sol** (`gpt-5.6-sol`) for planning, hard or critical implementation, and design or visual work.

## Details and upkeep

For pricing, API compatibility, multi-model patterns, and how to evaluate a choice, read [references/claude-models.md](references/claude-models.md). It holds everything that changes when models ship, so update it first and touch this file only if the advice itself changes.
