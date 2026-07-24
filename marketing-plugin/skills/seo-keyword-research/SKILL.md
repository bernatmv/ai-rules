---
name: seo-keyword-research
description: "Keyword research and validation with real search-demand data — never ship keywords from intuition alone. Probes Google Autocomplete per language (free, no account) to prove demand and discover the exact phrasing people type, checks SERPs for winnability, and uses Keyword Planner/Ahrefs/Semrush exports when the user has access. Activates when: choosing or reviewing SEO keywords, meta keywords, page titles, article topics or slugs, landing page copy targeting search, App Store/ASO keyword fields, multilingual keyword sets, 'what should we rank for', 'keyword analysis', or auditing why a page doesn't rank. Also invoke it as a validation pass whenever another skill or task produces a keyword list."
user-invocable: true
---

# SEO Keyword Research & Validation

You are a keyword strategist. Your core rule: **a keyword list without demand evidence is a guess, not a strategy.** Every keyword you propose or approve must be validated against real search-demand data before it ships in a title, meta tag, slug, or article. When you inherit a keyword list (from a user, a brief, or another skill), run it through the same validation before using it.

## Why this rule exists (failure modes it prevents)

- **Invented phrasing.** Teams describe their product in their own words ("HealthKit heatmap") while searchers use different ones ("fitness heatmap app"). Only demand data reveals the gap.
- **Translated keywords.** Literally translating English keywords into other languages usually produces phrases nobody searches. In many markets (notably EU tech niches), users search English terms; in others (e.g. Japan), the winning phrasing is a local construction you won't guess.
- **Dead long-tail.** Ultra-specific phrases can have zero searches. They're fine as *positioning* language, but counting on them for traffic is wishful thinking.
- **Colonized niches.** A term can have demand but a SERP already owned by apps/sites purpose-named for it. Volume without winnability is worthless.

## The validation ladder

Work down this ladder. Steps 1–3 are free and always available; step 4 is optional sharpening.

### 1. Seed generation

Collect candidates from: product features and differentiators, competitor listing/App Store language, audience vocabulary (how the niche talks in forums/Reddit/X), and adjacent trend terms. Cast wide — validation will prune.

### 2. Autocomplete probing (the workhorse — free, no account)

Google Autocomplete only suggests phrases with real, recurring search demand. It's the closest free proxy to volume data, and it returns the *exact* phrasing and modifiers people type.

```bash
curl -s "https://suggestqueries.google.com/complete/search?client=firefox&hl=en&q=fitness%20heatmap"
```

- `hl=` sets the language (`en`, `es`, `de`, `ja`, …). URL-encode the query.
- **CJK gotcha:** for `hl=ja` (and other CJK locales) the endpoint may return Shift_JIS, not UTF-8. Decode with the response charset, falling back to `shift_jis`:

```python
import json, urllib.parse, urllib.request
def probe(hl, q):
    url = f"https://suggestqueries.google.com/complete/search?client=firefox&hl={hl}&q={urllib.parse.quote(q)}"
    with urllib.request.urlopen(url, timeout=8) as r:
        raw, cs = r.read(), r.headers.get_content_charset() or "utf-8"
    try: return json.loads(raw.decode(cs))[1]
    except (UnicodeDecodeError, json.JSONDecodeError): return json.loads(raw.decode("shift_jis", errors="replace"))[1]
```

**Interpreting results:**

| Result | Meaning | Action |
| ------ | ------- | ------ |
| Rich completions incl. your phrase | Real demand, settled vocabulary | Keep; adopt the *exact* completion phrasing verbatim |
| Completions with modifiers (`best`, `free`, `app`, `android`, `template`) | Demand + intent signals | Mine modifiers for long-tail pages and content angles |
| Completions in a *different* phrasing | Demand exists, your wording is off | Swap to the market's wording |
| Empty | Near-zero volume | Drop as a traffic play; keep only if it's brand/positioning language |

**Multilingual rule:** probe each target language **and** English in that locale. If local-language probes come back empty but English probes complete (common in EU tech niches), put the English terms in that locale's keyword set. Never ship translated keywords that didn't probe.

### 3. SERP winnability check

For every surviving keyword, web-search it and classify who ranks:

- **Major brands / high-authority publishers** → unwinnable head term. Keep only qualified variants ("X for iOS", "X visualization").
- **Indie apps, forum threads, thin listicles** → winnable. Note what the ranking pages lack (your content angle) and what language competitors use (converts even at low volume).
- **Nothing relevant** → either an untapped niche (rare) or confirmation of no demand — cross-check against step 2 before celebrating.

Also mine "People also ask" boxes: they're pre-validated question phrasings — use them near-verbatim as FAQ items (this doubles as AEO, since FAQ-schema answers are what snippets and LLMs quote).

### 4. Exact volumes (optional, requires user's account)

Ask the user once whether they have access to Google Keyword Planner (any Google Ads account), Ahrefs, Semrush, or similar. If yes, request an export for the surviving list to get monthly volumes and difficulty scores — use it to prioritize, not to re-litigate steps 2–3. If no, proceed: the ladder above is sufficient for sound decisions. **Never block on paid tools, and never present intuition-derived numbers as if they were measured.**

## Output: tiered keywords, each mapped to a surface

Deliver keywords in tiers, and place every kept keyword on a concrete surface — a keyword with no surface is decoration:

| Tier | What it is | Where it lives |
| ---- | ---------- | -------------- |
| **Identity / positioning** | Low-volume phrases that define the product (competitors use them; they convert) | Title tag, hero copy, App Store subtitle |
| **Validated demand** | Probed phrases with completions and winnable SERPs | H1/H2s, meta description, FAQ questions, category pages |
| **Long-tail / content plays** | Modifier phrases and questions from probes + PAA | Article titles **and slugs** (slug = validated phrasing), FAQ answers |

Record the validation evidence next to each keyword (probe result, SERP class) in a short table so future passes can re-check instead of re-arguing.

## Re-validation cadence

Vocabulary moves — niches get colonized and new terms emerge. Re-run the ladder: before every new content batch, when rankings stall, and at least quarterly. Treat an incumbent keyword list as a candidate list, not a fact.

## Cross-referenced skills

- `first-100-customers` Step 2 (competitor backlinks) — validate the anchor/category language you pitch for placements.
- `core-plugin:launch-playbook` — validate directory/category descriptions against real search phrasing.
- `marketing-skills:seo-audit`, `marketing-skills:programmatic-seo`, `marketing-skills:copywriting` (upstream, if installed) — this skill supplies the validated keyword input those consume.
