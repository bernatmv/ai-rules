# Lessons from a real production economy

Concrete failure modes observed in a real, large, shipped Roblox economy. Each is a trap
to avoid, paired with the architecture pattern that prevents it. These are *why* the
chassis is shaped the way it is — not hypotheticals.

## 1. No single currency authority → the same guard logic copied everywhere

Currency was a `leaderstats` IntValue written directly (`cash.Value += amount`) by a dozen
different services (income, offline earnings, rewards, codes, purchases, admin tools…).
Each write site had to *manually* call a shared anti-cheat "whitelist this gain" function
**before** the write, or the anti-cheat clawed the currency back.

- **Why it's bad:** forget the call once → either a legit reward is clawed back
  (false-positive) or a validation path is skipped. The guard logic is duplicated, not
  owned by one place.
- **Fix:** the **single currency authority** (architecture.md Core 3). The anti-cheat hook
  (`onGrant`) lives *inside* the one write path, so it can never be forgotten. A dozen
  manual calls → zero.

## 2. Multiplier stacking hardcoded in more than one place

The earnings multiplier was a fixed chain in one function — `rebirth * gamepass * item *
pet` — and a *second*, different chain applied elsewhere (at collection time). Adding any
new boost meant editing central functions in multiple spots and hoping every application
site was caught.

- **Why it's bad:** every new modifier touches shared code; the parallel chains drift;
  it's the exact "gets really confusing" complaint.
- **Fix:** the **modifier aggregation pipeline** (Core 1). Sources register modifiers; math
  aggregates in one order-independent place; a new boost is one registration call.

## 3. Global (`_G`) coupling and load-order races

Services found each other through globals — `_G.EconomyService`, `_G.SomeOtherService` —
with spin-waits like `repeat task.wait() until _G.X`.

- **Why it's bad:** invisible dependencies, fragile boot order, hard to test or reason
  about.
- **Fix:** **signals + explicit requires** (rule 5). Systems subscribe to events; no global
  lookups.

## 4. Datamodel as the source of truth

State lived in `leaderstats` IntValues + instance attributes, so persistence had to mirror
values back and forth between the save and the datamodel, with special cases to avoid
clobbering values the save had just restored.

- **Why it's bad:** two sources of truth (save vs datamodel) that must be kept in sync;
  every sync gap is a bug surface.
- **Fix:** **`profile.Data` is authoritative, leaderstats is a read-only mirror** (integrates
  with the roblox-datastore skill). One source of truth; display is derived.

## The through-line

None of these were "bad code" in isolation — they're what happens when an economy grows
without a chassis. Every mechanic added its own write path, its own multiplier line, its
own global. The architecture in this skill exists specifically so that the 13th mechanic
costs one config entry and one registration call, not another copy of the ritual.
