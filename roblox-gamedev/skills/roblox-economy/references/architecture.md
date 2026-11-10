# Economy architecture — the anti-sprawl chassis

Structural patterns only. **No currency names, stats, or numbers are hardcoded here** —
those come from the interview and live in `EconomyConfig`. This is *how* to arrange an
economy so it never turns into spaghetti, regardless of what the economy is.

The three cores below (aggregation, luck roll, currency authority) were verified with
assertions in a live Studio session — the code is correct, not illustrative.

## The five rules

1. **One currency authority.** Every currency change goes through `CurrencyService`.
   Nothing else writes a balance.
2. **One modifier pipeline.** All stat math aggregates in `ModifierService`. Sources
   *register* modifiers; they never edit central math.
3. **Rolls are separate.** Luck/rarity/mutation live in `RollService`, not mixed into
   modifier math.
4. **Data-driven.** Currencies, stats, rarities, mutations, curves are config tables.
   Adding an item/rarity/boost is a data edit, not new logic.
5. **Signals, not `_G`.** Systems react to `CurrencyChanged` / `ItemObtained` etc.
   No global lookups, no load-order races.

Source of truth = in-memory `profile.Data` (from the roblox-datastore skill), mirrored
to `leaderstats` for display. Persistent things (currencies, rebirth count, owned
passes) live in `PROFILE_TEMPLATE`; runtime modifiers are re-registered from them on join.

## Config shape (filled from the interview)

```lua
-- ReplicatedStorage/EconomyConfig/Currencies  (Q4-6). Names are the DEV'S, not defaults.
return {
    -- <CurrencyKey> = { display = "...", leaderstat = true/false, default = 0 }
}
-- EconomyConfig/Stats  (Q8-11): the modifier targets.
return {
    -- <StatKey> = { base = 1, clamp = { min = 0, max = <Q11 budget> } }
}
-- EconomyConfig/Rarities  (Q12): roll table. `rare = true` is what luck biases.
return {
    -- { name = "...", weight = <n>, rare = <bool> }, ...
}
```
Every `<Key>` above is placeholder — instantiate from the dev's answers. Currency keys
must also exist in the roblox-datastore `PROFILE_TEMPLATE`.

## Core 1 — modifier aggregation  (VERIFIED)

`base -> +sum(additive) -> *product(multiplicative) -> highest-priority override -> clamp`.
Order-independent: a source can register a modifier without knowing what else exists.

```lua
local function aggregate(base, modifiers, clamp)
    local add, mult = 0, 1
    local override, overridePriority = nil, -math.huge
    for _, m in ipairs(modifiers) do
        if m.type == "Additive" then add += m.value
        elseif m.type == "Multiplicative" then mult *= m.value
        elseif m.type == "Override" then
            local p = m.priority or 0
            if p >= overridePriority then override, overridePriority = m.value, p end
        end
    end
    local v = (base + add) * mult
    if override ~= nil then v = override end
    if clamp then
        if clamp.min then v = math.max(clamp.min, v) end
        if clamp.max then v = math.min(clamp.max, v) end
    end
    return v
end
```

`ModifierService` wraps this with state (adapt as needed):

```lua
-- store[entity][statKey] = { [id] = { value, type, source, tags, priority } }
-- API: Add(entity, statKey, spec) -> id | RemoveById(id) | RemoveBySource(entity, statKey, source)
--      RemoveByTag(entity, tag) | Get(entity, statKey) | .Changed signal
-- Get() reads base+clamp from EconomyConfig.Stats, aggregates, caches with a dirty flag
--   that clears when a modifier for that (entity, statKey) changes.
-- stackRule on a spec: "Replace" -> RemoveBySource before adding (equipment swap);
--   default -> stack. Clear(entity) on PlayerRemoving.
```

**Adding a new boost = 3 steps, zero central edits:** (1) define it as data, (2)
`Modifier.Add(player, "<StatKey>", spec)` on the trigger, (3) systems read
`Modifier.Get(...)` and update via the `.Changed` signal.

## Core 2 — luck-biased roll  (VERIFIED)

Luck scales rare weights; O(1) per roll, never reroll-N-times.

```lua
local function weightedRoll(entries, luck, rng)
    luck = math.max(1, luck or 1)
    local total, weights = 0, {}
    for i, e in ipairs(entries) do
        local w = e.weight * (e.rare and luck or 1)
        weights[i] = w; total += w
    end
    local r = rng:NextNumber(0, total)
    local acc = 0
    for i, e in ipairs(entries) do
        acc += weights[i]
        if r <= acc then return e end
    end
    return entries[#entries]
end
```

`RollService` adds pity on top (recommended whenever there's RNG):

```lua
-- pity[entity][tableName] = misses. WithPity(entity, tableName, entries, luck, threshold, rng):
--   if misses >= threshold -> force a weighted pick among rare entries, reset to 0.
--   else weightedRoll; reset on rare, increment on miss. ClearPity(entity) on leave.
```

## Core 3 — single currency authority  (VERIFIED)

The one write path. Anti-cheat whitelist (`onGrant`) + `Changed` signal happen *inside*,
so no caller can forget them — this is the direct fix for the "call grant() everywhere
or it breaks" sprawl (see lessons-from-production.md).

```lua
-- Get(player, name) -> profile.Data[name]
-- set(player, name, value, reason): clamp >=0, write profile.Data (truth), mirror to
--   leaderstats if config.leaderstat, fire Changed(player, name, new, old, reason)
-- Add(player, name, amount, reason): if amount>0 and onGrant then onGrant(...) end; set(cur+amount)
-- Remove(player, name, amount, reason): fail if cur<amount; else set(cur-amount)
-- CanAfford(player, name, cost) -> cur >= cost
-- CurrencyService.onGrant = your anti-cheat hook (set once). Currency names from config.
-- On PlayerAdded: mirror each config currency from profile.Data to leaderstats.
```

Verified behavior: source of truth and mirror stay in sync, overspend is blocked, and
`onGrant` fires exactly once per grant from the single path.

## Minimal signal (no `_G`, no Instance)

```lua
local Signal = {} ; Signal.__index = Signal
function Signal.new() return setmetatable({_h={}}, Signal) end
function Signal:Connect(fn) local h={fn=fn}; table.insert(self._h,h)
    return { Disconnect=function() local i=table.find(self._h,h); if i then table.remove(self._h,i) end end } end
function Signal:Fire(...) for _,h in ipairs(table.clone(self._h)) do task.spawn(h.fn, ...) end end
return Signal
```

## Assembly example (the common idle loop) — built from the chassis, not hardcoded

For "items generate income/sec" games, the loop is: each tick, sum equipped items'
`ValuePerSec`, multiply by `Modifier.Get(player, "<IncomeStat>")`, and bank via
`Currency.Add(player, "<Currency>", amount, "income")`. The stat name and currency name
are whatever the interview produced. Rebirth/pets/passes each `Modifier.Add` into
`<IncomeStat>` — the tick never changes when a new boost is added.
