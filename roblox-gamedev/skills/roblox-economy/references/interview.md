# The economy interview

**Run this BEFORE writing any economy code.** Never assume the game's currencies,
mechanics, or numbers — extract them. Ask in batches (don't fire all 20 at once);
lead with the core-loop questions, then go deeper where the answers point.

If the dev doesn't code (common), phrase questions in plain design language, not Luau.
Offer concrete options and a recommendation rather than open-ended prompts.

## A. Genre & core loop (ask first — this shapes everything)

1. What genre / reference games? (idle-simulator, tycoon, RNG-chase, trading, RPG…)
2. The core loop in one sentence: "the player does ___ to earn ___ to buy ___."
3. Target session shape: quick 5-min bursts, or long 1hr+ sessions? (drives curve tuning)

## B. Currencies, sources & sinks

4. How many currencies, and what is **each one's job**? (grind / premium / prestige)
5. Primary **sources** — how does currency enter? (income/sec, drops, rewards, codes)
6. Primary **sinks** — what destroys it? (upgrades, rebirths, rolls, cosmetics)
   → If they can't name 3+, raise the mid-game-cliff risk.
7. Anything **tradeable/giftable** between players? (yes → mandates session locking in
   the data layer — see the roblox-datastore skill)

## C. Modifiers & stacking (income/multiplier math)

8. List every multiplier/boost you foresee (rebirth mult, 2x gamepass, pet bonus,
   event weekend, VIP…). For each: what stat does it boost?
9. For each: **additive or multiplicative**? And when two of the same source apply —
   do they **stack, replace, or keep-highest**?
10. Any **override** states? (stun sets income to 0, event locks a value)
11. What's the **maximum realistic stacked multiplier** you'll allow? (forces a budget)

## D. Rarity / rolls / luck / mutations (only if the game has RNG)

12. Rarity tiers and rough odds for the rarest?
13. How does **luck** work — bias the table (recommended) or reroll? Permanent
    (gamepass) or temporary (potion/ad)?
14. **Pity**: guarantee a rare after N failures? (recommend yes)
15. **Mutations/variants** on items? Do they multiply value, and can they stack?

## E. Progression & prestige

16. Cost-curve feel, or "how long until the first big upgrade"?
17. **Rebirth/prestige?** What resets, what carries over, what's the reward?
18. What content is **gated behind each prestige tier**? (the retention engine)
19. Where should progress deliberately **slow** (soft caps)?

## F. Monetization & persistence

20. What's monetized, and does any of it cross into **pay-to-win**?
21. Expected data size / inventory complexity? (confirms the persistence needs; economy
    save schema plugs into the roblox-datastore skill's PROFILE_TEMPLATE)

## Turning answers into a build

- **Currencies (Q4–6)** → `EconomyConfig/Currencies` entries + keys in the
  PROFILE_TEMPLATE (roblox-datastore skill).
- **Modifiers (Q8–11)** → `EconomyConfig/Stats` (statKeys + base + clamp) + each source
  becomes a `Modifier.Add(...)` registration. The max multiplier (Q11) → clamp.max.
- **Rolls (Q12–15)** → `EconomyConfig/Rarities` + `Mutations`; luck (Q13) feeds
  RollService; pity (Q14) → threshold.
- **Progression (Q16–19)** → `EconomyConfig/Progression` (cost curve, rebirth reqs,
  tier gates).
- **Trading (Q7)** → require session locking in the data layer.

Then scaffold only the modules the answers justify — a simple idle game may need
Currency + Modifiers and no roll system at all. Don't build layers they didn't ask for.
