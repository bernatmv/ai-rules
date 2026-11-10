---
name: roblox-economy
description: Design and build a Roblox game's economy from the developer's own vision — currencies, income, luck/rarity/mutations, modifiers, progression, rebirths, shops, sinks. Use when starting economy work on a game, adding an economy mechanic (multiplier, boost, luck, rebirth, roll), or when an economy feels grindy, broken, inflated, or has sprawled across too many scripts. Interviews first, applies economy design knowledge, and scaffolds an anti-sprawl architecture with NO hardcoded currencies or numbers.
---

# Roblox economy (design partner, not a template)

This skill does **not** drop a fixed economy into a game. Every game's economy is
different. It **interviews the developer to extract their vision**, brings the design
judgment to make it good, and scaffolds a **structure that never turns into spaghetti** —
with zero hardcoded currencies, mechanics, or numbers.

The only thing that is fixed is *architecture* (how to arrange the code). All *content*
comes from the interview.

## The workflow — follow in order

1. **Interview first.** Do NOT write economy code before running
   [references/interview.md](references/interview.md). Never assume the currencies,
   mechanics, or numbers — extract them. Ask in batches, lead with the core-loop
   questions. If the dev doesn't code, use plain design language and offer options + a
   recommendation.
2. **Apply the design knowledge.** Use [references/economy-design.md](references/economy-design.md)
   to shape the answers and to **push back honestly** when a choice is risky (the three
   most common: don't slow the early game for retention; luck/rarity ≠ income multipliers;
   more multiplier layers ≠ more depth).
3. **Scaffold to the answers** using [references/architecture.md](references/architecture.md).
   Instantiate config from what the dev said; build only the modules the answers justify
   (a simple idle game may need Currency + Modifiers and no roll system at all — don't
   add layers they didn't ask for).
4. **Avoid the known traps** in [references/lessons-from-production.md](references/lessons-from-production.md)
   — real failure modes from a shipped game, each with the pattern that prevents it.

## Non-negotiables (regardless of the game)

- **Server-authoritative.** Client sends actions, never balances.
- **One currency authority** — every balance change goes through `CurrencyService`.
- **One modifier pipeline** — stat math aggregates in one place; sources *register*
  modifiers, they don't edit central math.
- **Rolls are a separate system** from modifiers (luck/rarity/mutation ≠ income math).
- **Data-driven + signals, not `_G`.**
- **`profile.Data` is the source of truth**, `leaderstats` is a display mirror.
- **No hardcoded currencies, stats, or numbers** — all from the interview + config.

## Integrates with the data layer

The economy's persisted values (currencies, rebirth count, owned passes) are keys in the
`PROFILE_TEMPLATE` of the **roblox-datastore** skill. Set that up first (or alongside);
`CurrencyService` reads/writes `profile.Data` via its `PlayerDataManager`. If the game has
trading/gifting, the data layer MUST use session locking.

## What's verified

The three load-bearing structural cores in architecture.md were run with assertions in a
live Studio session:
- **Modifier aggregation** — `(base + additives) * multipliers`, override, clamp;
  order-independent. ✓
- **Luck-biased roll** — rare rate rises monotonically with luck (measured
  ~0.21 → 0.72 → 0.93 at luck ×1 / ×10 / ×50). ✓
- **Single currency authority** — source of truth + mirror stay in sync, overspend
  blocked, anti-cheat hook fires exactly once from the one write path. ✓

To re-verify after adapting the patterns, paste the core functions from architecture.md
into `execute_luau` (datamodel `Edit`) with assertions, exactly as done for the originals.

## What this skill can't do

It gives an un-spaghettifiable chassis + the design conversation. It **cannot balance the
economy for you** — the numbers (cost curves, drop odds, multiplier budget, gating) are
90% of whether the game is fun and are tuned iteratively against real player data. Say so
to the dev; don't pretend defaults are balanced.
