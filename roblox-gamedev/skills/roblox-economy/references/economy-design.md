# Economy design knowledge

The judgment to bring to any economy. None of this prescribes *what* the game's
economy is — it's how to tell a good design from one that will churn players. Use it
to inform the interview and to push back honestly when a requested choice is risky.

## Non-negotiables (true for every game)

- **Server authority.** The client sends *actions* ("I collected a coin", "I bought
  X"), never *state* ("I now have 500 coins"). The server owns all currency/stat
  values. Any economy that trusts client-reported balances is exploitable.
- **One source of truth per value.** A currency lives in exactly one place
  (in-memory `profile.Data`, mirrored to leaderstats for display). Never let multiple
  systems each hold their own copy.

## Sources vs sinks — sinks ARE the game

- **Sources** = where currency enters (drops, income/sec, rewards, codes).
- **Sinks** = what *destroys* it (upgrades, rebirths, gacha rolls, cosmetics).
- Analyze every sink by **what it removes**, not what it gives. A sink is a converter:
  soft currency → permanent power, wallet → cosmetic status, a whole run → a meta bonus.
- Three failure modes to design against:
  1. Source outpaces sink → **inflation**, progress feels meaningless.
  2. Conversion rate mistuned → bad pacing feel.
  3. Currency stops feeling scarce → players stop perceiving cost.
- **Litmus test in the interview:** if they can't name 3+ meaningful sinks, flag the
  mid-game-cliff risk now.

## Progression pacing

- **Shape:** fast early, steady mid, slow late. Produced by an **exponential cost
  curve** (`cost = base * growth^level`, growth ~1.07–1.15) which keeps the *time
  between purchases* roughly constant even as raw numbers balloon.
- **Soft caps beat hard caps** — rising cost / diminishing returns, not walls.
- **Front-load dopamine.** The early game must feel FAST.

## Retention engines (offer these; don't impose them)

- **Rebirth / prestige loop** — reset progress for a permanent multiplier and gate new
  content behind tiers. Simultaneously a mega-sink and a content gate. The single most
  reliable retention mechanic for idle/simulator games.
- **Multiple currency layers** — soft (grind), hard/premium, prestige — so sinks stay
  meaningful at every stage.
- **Rarity chase + mutations** — "Golden/Shiny/Rainbow" variants multiply the perceived
  value of items the player already has. Cheap content that extends the chase.
- **Pity system** — guarantee a rare after N unlucky rolls. Removes the tail of players
  who roll forever and quit. Strongly recommend it whenever there's RNG.

## Luck, rarity, mutations — a distinct system from multipliers

- Luck should **bias the weights** of a roll table (scale rare weights up), which is
  O(1) per roll. Do NOT implement luck as "reroll N times, keep the rarest" — that's
  linear in luck and tanks performance at high luck.
- These are **roll-table inputs**, not stat modifiers. Keep them in a separate system
  from income/multiplier math (see architecture.md). Conflating them is a top cause of
  economy spaghetti.

## Honest pushbacks (say these when they come up)

1. **"Slow the early game so players don't rush to endgame"** → backwards. Retention
   dies at the **mid-game cliff**, not from reaching endgame. Make early game fast;
   stop rushing with **rebirth-gated content + soft caps**, not first-session friction.
2. **"Luck + rarities + mutations + income boosts are all one economy system"** → no,
   they're two: a **modifier pipeline** (income/multipliers) and a **roll system**
   (luck/rarity/mutation). Building them as one is why past code sprawled.
3. **"More modifier layers = more depth"** → more layers stacking multiplicatively =
   runaway inflation. A clean architecture makes adding layers *easy*, which is a trap.
   Budget the maximum stacked multiplier deliberately.

## Reusable vs bespoke

- **Reusable (the skill provides):** the architecture — single currency authority,
  modifier aggregation pipeline, roll system, data-driven config, signal decoupling,
  profile.Data-as-truth. Guarantees the code never sprawls.
- **Bespoke (comes from the interview, per game):** every number and name — currencies
  and their jobs, cost curves, drop odds, multiplier budget, prestige/content gating,
  the core loop itself. This is 90% of whether the game is fun and cannot be templated.
- **Bottom line to tell the dev:** the skill gives an un-spaghettifiable chassis + the
  design conversation. It cannot balance the economy — that's iterative tuning against
  real player data.
