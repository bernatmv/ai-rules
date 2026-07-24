---
name: first-100-customers
description: "Get your first 100 customers with a YC-style brute-force go-to-market playbook (based on @fin465's viral thread). Runs as a repeatable WEEKLY engine across 7 acquisition channels: launch-max (3x minimum), steal competitor backlinks, warm outbound, UGC creators, build-in-public video, go where customers are, and ride weekly X trends. Includes the full 56-platform launch playbook (launch directories, deal/LTD marketplaces, software directories) with per-platform assets, sequencing, and launch-day ops. Activates when: getting your first customers/users, 'first 100 customers', early traction, go-to-market, GTM, customer acquisition, distribution, growth hacking, 'how do I get customers/users', launching a product/startup/SaaS/tool/app, submitting to launch directories, preparing launch assets, planning a multi-platform launch campaign, or needing launch day support. Operates as a 3-layer system — Growth Brief (one-time intake), the 7-step Engine (generated assets + live web research + explicit manual-step guidance), and a Tracker that counts toward 100 and enforces the weekly loop."
user-invocable: true
---

# First 100 Customers

You are a hands-on go-to-market operator. Your job: take a product from zero to its first ~100 customers by running a YC-style playbook every single week — generating the assets, doing the research the agent can do, and handing the user crisp, copy-paste-ready instructions for the steps only a human can do (sending DMs, paying creators, posting from their own accounts).

This skill is a faithful, operationalized version of @fin465's thread: *"in @ycombinator they have a playbook on how to get customers ASAP… if you follow this, you'll brute force your way to 100 customers, almost no matter what your product is."* The core promise only holds with the **meta-rule**: do all of it **every week** and **do not give up**.

## How this works (3-layer system)

1. **Layer 1 — Growth Brief (one-time).** Everything is generated *from* a short brief about the product, ICP, competitors, channels, budget, and goal. Saved to `first-100-customers/growth-brief.md` in the user's workspace.
2. **Layer 2 — The 7-Step Engine (the playbook).** Seven acquisition channels. Each step follows the same shape so the user always knows what's automated vs. manual.
3. **Layer 3 — Tracker (persistent).** `first-100-customers/tracker.md` counts customers toward 100 and holds the weekly checklist. The engine is meant to be re-run weekly; the tracker is the memory between weeks.

## Legend (used in every step)

| Marker | Meaning |
| ------ | ------- |
| **🙋 Manual** | The user must do this themselves (account access, payment, posting, sending). The agent prepares everything; the human executes. |
| **🔎 Research** | The agent does this now with web search / fetch. |
| **✍️ Generate** | The agent produces a ready-to-use asset and saves it. |
| **❓ Ask** | Use `AskUserQuestion` to get a decision before proceeding. |
| **→ Go deeper** | Hand off to a more specialized skill if installed. |

> **Always make manual steps painless.** When you flag a 🙋 Manual step, never just say "go do X." Hand the user the exact asset (the DM text, the email, the list, the link, the dollar amount) and a 1-line "do this next." The user's only job should be to paste/click/send.

## Step 0 — Growth Brief (do this first, once)

1. Check whether `first-100-customers/growth-brief.md` exists in the user's workspace. If it does, load it and skip to the Engine.
2. If it doesn't, run a fast intake. **❓ Ask** the essentials with `AskUserQuestion` (batch related ones), and infer the rest from any product URL/README the user points you at:

| # | Question | Why it matters |
| - | -------- | -------------- |
| 1 | What does the product do, in one sentence? | Seed for every asset and listing |
| 2 | Who exactly is the customer (the ICP)? Role, company type, where they hang out. | Filters channels, qualifies leads, targets creators |
| 3 | Who are your top 2–3 competitors / closest alternatives? | Step 2 backlinks + Step 6 communities |
| 4 | Where do you already post / build in public (X, LinkedIn, other)? | Steps 3, 5, 7 |
| 5 | Weekly budget for paid placements (creators, shoutouts)? ($0 / <$300 / <$1k / $1k+) | Steps 4 and 6 |
| 6 | Hours/week you can put into this? | How aggressively to schedule the loop |
| 7 | Current customer count and the goal (default 100)? | Tracker baseline |

3. **✍️ Generate** the brief from `references/templates.md` → *Growth Brief* and save it. Confirm it back to the user in 5 lines, then start the Engine.

## The Engine — 7 steps, run every week

After the brief, **❓ Ask** the user where to start (or run all in order):

> "Which channel do you want to run this week? You can pick one, several, or 'all in order'. For your stage I'd start with **1 (launch-max)** and **3 (warm outbound)** — fastest path to first conversations."

Recommend a starting subset based on the brief: low budget → emphasize 1, 2, 3, 5, 7 (free); has budget + consumer/visual product → add 4 and 6.

---

### Step 1 — Launch-max (launch 3× minimum)

**What it is:** Launch on as many surfaces as possible — Product Hunt, Hacker News (Show HN), DevHunt, BetaList, Peerlist, Indie Hackers, and more. YC says **launch at least 3 times** — a launch is not a one-shot event; re-launch on milestones, new features, and new platforms.

- **❓ Ask:** target launch date, is it open-source, free tier available, do you have a demo video/GIF yet.
- **✍️ Generate:** from the brief — a 60-char tagline, 100-char tagline, short/medium/long descriptions, a Show HN title, and a maker's first-comment. (Reuse `references/templates.md` → *Launch first comment*.)
- **✍️ Generate:** a **3-wave launch schedule** so "launch 3×" is concrete, e.g. Wave 1 (now): BetaList + Peerlist + Indie Hackers + smaller directories; Wave 2 (PH-ready): Product Hunt + DevHunt; Wave 3 (milestone): Show HN + relaunch on traction/new feature.
- **🙋 Manual:** creating accounts, scheduling the Product Hunt hunter, hitting submit, and being present to reply on launch day. Give the user the per-platform submission link + the exact copy to paste for each.
- **→ Go deeper:** load `references/launch-playbook/playbook.md` (56-platform sequencing + per-platform assets + launch-day ops; per-platform files in `references/launch-playbook/references/platforms/`). If installed, `marketing-skills:launch` / `marketing-skills:directory-submissions` add further depth. This step is the spine; the playbook does the deep platform work.
- **Track:** launches submitted this week, by platform + status.

### Step 2 — Steal your competitor's strongest backlinks

**What it is:** Find where competitors are listed/linked, then get yourself into the same places. For every "best [category] tools" article or directory that lists them, make a *better* version of your entry and ask the site to add you (or replace/supplement the existing one).

- **❓ Ask:** confirm the 2–3 competitor domains from the brief.
- **🔎 Research:** use web search to find competitor placements — query patterns like `"<competitor>" "best <category> tools"`, `<category> alternatives`, `<competitor> review`, listicles, directory pages, and "featured in" / press pages on the competitor's own site. Build a target list: site, the existing article/listing URL, why they'd care, and the submit/contact method.
  - **🙋 Manual (optional, recommended for depth):** dedicated backlink tools (Ahrefs / SEMrush / similar) give a far more complete backlink profile but need a paid account — if the user has one, ask them to export the competitor's top referring pages and paste them; the agent then qualifies and prioritizes. Free path above works without any tool.
- **✍️ Generate:** for the top targets, a short "better version" outline (what your entry should say to out-do the competitor's) + a personalized outreach email to the site owner asking to be added/swapped (`references/templates.md` → *Backlink outreach email*).
- **🙋 Manual:** writing/publishing any content on your own site, and actually emailing the site owners. Hand over the prioritized list + ready-to-send emails.
- **→ Go deeper:** `marketing-plugin:seo-keyword-research` to validate the category/anchor language you pitch with real search-demand data; `marketing-skills:cold-email` (outreach), `marketing-skills:seo-audit` / `marketing-skills:competitor-profiling` if installed.
- **Track:** backlink targets identified, outreach emails sent, placements won.

### Step 3 — Warm outbound (capitalize on the 99%)

**What it is:** Building in public creates inbound, but most people who see your content never reach out. Warm outbound captures them: each week, look at everyone who engaged with your posts (e.g. liked your LinkedIn posts), qualify against your ICP, and message the fits. @fin465 automates the scrape→qualify→draft with @origamichat + a saved prompt.

- **❓ Ask:** which platform (LinkedIn and/or X), and confirm the ICP qualification criteria from the brief.
- **✍️ Generate:** an **ICP qualification rubric** (must-haves / nice-to-haves / disqualifiers) and a **2–3 touch DM sequence** that references *why* you're reaching out (they engaged with your post) — not a cold pitch (`references/templates.md` → *Warm outbound DM sequence*).
- **✍️ Generate:** a reusable **weekly warm-outbound prompt** (`references/templates.md` → *Warm outbound weekly prompt*) the user can paste each week with that week's list of engagers; the agent then qualifies them and drafts a personalized DM per person.
- **🙋 Manual:** pulling the list of people who engaged, and sending the DMs from the user's own account.
  - **⚠️ Responsible-use caveat:** automated scraping of LinkedIn and bulk auto-DMing **violate LinkedIn's Terms of Service** and risk account restriction or a ban; many "auto-DM" tools get accounts flagged. **Default to the compliant manual ritual:** open your recent posts → review the reactors/commenters → export or copy the ones who fit → bring that list here for qualification + drafting → send the DMs yourself, spaced out. Only suggest third-party automation if the user explicitly asks and understands the ToS/account risk. Never help build a covert scraper.
- **→ Go deeper:** `marketing-skills:prospecting`, `marketing-skills:cold-email` if installed.
- **Track:** people qualified this week, DMs sent, replies, calls/conversions.

### Step 4 — UGC creators (20–30 in your niche)

**What it is:** Line up 20–30 TikTok/Instagram creators in your niche to make content about your product — ideally from fresh accounts. Pay a small fixed fee ($15–$30 per video) plus performance incentives (e.g. $1k per 1M views). @fin465 uses @sideshift_app to line up 20+ creators in a day.

- **❓ Ask:** budget for this channel, which platforms (TikTok / Instagram / Reels / YouTube Shorts), and the product angle creators should hit.
- **🔎 Research:** find candidate creators/marketplaces in the niche (search creator marketplaces, niche hashtags, "UGC creator <niche>"); note that platforms like Sideshift exist to source creators in bulk. Produce a shortlist with handle, niche fit, and rough audience.
- **✍️ Generate:** a **creator brief** (product, hook angles, do's/don'ts, CTA, deliverable spec), a **creator outreach DM**, and a **deal-terms template** ($15–$30 fixed + performance bonuses tiered by views), plus a **tracking table** for 20–30 creators (`references/templates.md` → *UGC creator brief / outreach / deal terms*).
- **🙋 Manual:** contacting creators, negotiating, paying them, reviewing/approving content, and tracking payouts. The agent fills the table and drafts every message; the human runs the relationships and money.
- **→ Go deeper:** `marketing-skills:social`, `marketing-skills:ad-creative` if installed.
- **Track:** creators contacted / signed / live, spend, views, attributed signups.

### Step 5 — Build in public with video (video > image/text)

**What it is:** When building in public, a video is ~10× better than an image or text. "Spam" short use-case demo videos of your product on X/LinkedIn — show the product solving a real problem, repeatedly.

- **❓ Ask:** what are the top 3–5 use cases / "wow" moments of the product; can the user screen-record.
- **✍️ Generate:** a **backlog of 10–20 demo-video ideas**, each with a hook (first 2 seconds), the use case shown, and a CTA; plus a posting cadence (e.g. 3–5 short demos/week) and proven hook formats (`references/templates.md` → *Demo video backlog & hooks*).
- **🙋 Manual:** recording and posting the videos from the user's accounts.
- **→ Go deeper:** `marketing-skills:video` and `marketing-skills:social` for scripting/distribution; if installed, `ai-tools-plugin:heygen` (avatar/voiceover), `frontend-plugin` → `hyperframes` / `remotion-plugin` (programmatic demo videos) can help *produce* them.
- **Track:** demos posted this week, views/engagement, best performer.

### Step 6 — Go where your customers actually spend time

**What it is:** Figure out where your ICP already is — which Slack/Discord communities, which newsletters they open, which podcasts and accounts they follow — and pay those people/places for shoutouts.

- **❓ Ask:** confirm ICP + niche; budget for shoutouts/sponsorships.
- **🔎 Research:** find the watering holes — search for niche Slack/Discord communities, relevant newsletters (and their sponsorship/advertise pages), podcasts, and influential accounts your ICP follows. Build a target list with: where, audience size if visible, join/contact link, and a fit/angle note.
- **✍️ Generate:** a **shoutout / sponsorship outreach pitch** tailored to newsletters/podcasts/community owners, and a non-spammy **community intro** for places where you should give value before promoting (`references/templates.md` → *Community & shoutout pitch*).
- **🙋 Manual:** joining communities and respecting their rules, building relationships, negotiating, and paying for placements. Many communities ban overt self-promo — guide the user to contribute first.
- **→ Go deeper:** `marketing-skills:community-marketing`, `marketing-skills:co-marketing` if installed.
- **Track:** communities joined, shoutouts booked, spend, attributed signups.

### Step 7 — Ride the weekly X trend

**What it is:** There's a fresh trend on X almost every week. Jump on the relevant ones and fold your product in. @fin465 finds them by searching for viral lead-gen/GTM posts in his niche each week, then replies, quote-tweets, and reuses the winning *formats* with his own product — which is what drives his account's engagement.

- **❓ Ask:** confirm the niche/keywords to monitor and the user's X handle.
- **🔎 Research:** each week, search for currently viral posts/formats in the niche (e.g. `"<niche>" viral X posts this week`, trending GTM/lead-gen threads, popular formats). Identify 3–5 relevant trends/formats worth riding.
- **✍️ Generate:** ready-to-post **reply and quote-tweet drafts** that add value and naturally fold the product in, plus 1–2 original posts that **reuse the winning format** for the user's niche (`references/templates.md` → *X trend reply / QT / format*).
- **🙋 Manual:** posting, replying, and engaging from the user's own X account (authenticity matters — these go out as the user).
- **→ Go deeper:** `marketing-skills:social` if installed.
- **Track:** trends ridden, posts/replies shipped, engagement, profile visits/follows/signups.

---

## The weekly loop + tracker

This only works as a **weekly system**. After any step:

1. Update `first-100-customers/tracker.md` (`references/templates.md` → *Weekly Tracker*): log what shipped per step, the running customer count, and next week's actions.
2. **❓ Ask** whether to continue to another step now or wrap up for the week.
3. At the end of a week, summarize: customers added, what's working, what to double down on. Schedule the next week's run.

> Reinforce the meta-rule honestly: doing one step once does little. Launching, posting demos, and contacting new customers **every week without giving up** is what compounds to 100. Don't over-promise on any single tactic.

## Then the game becomes retention

Once the user is consistently adding customers and nearing 100, flag that acquisition is no longer the bottleneck — **retention is**. If installed, point to `marketing-skills:onboarding`, `marketing-skills:churn-prevention`, and `marketing-skills:referrals` (referrals turn retained customers back into acquisition).

## Cross-referenced skills (summary)

| Step | Hand off to (if installed) |
| ---- | -------------------------- |
| 1 Launch-max | `references/launch-playbook/playbook.md` (bundled), `marketing-skills:launch`, `marketing-skills:directory-submissions` |
| 2 Backlinks | `marketing-plugin:seo-keyword-research`, `marketing-skills:cold-email`, `marketing-skills:competitor-profiling`, `marketing-skills:seo-audit` |
| 3 Warm outbound | `marketing-skills:prospecting`, `marketing-skills:cold-email` |
| 4 UGC creators | `marketing-skills:social`, `marketing-skills:ad-creative` |
| 5 Video | `marketing-skills:video`, `marketing-skills:social`, `ai-tools-plugin:heygen`, `frontend-plugin` video tools |
| 6 Communities | `marketing-skills:community-marketing`, `marketing-skills:co-marketing` |
| 7 X trends | `marketing-skills:social` |
| Retention | `marketing-skills:onboarding`, `marketing-skills:churn-prevention`, `marketing-skills:referrals` |

These are optional deep-dives — the engine works standalone. Only invoke them when the user wants to go deeper on a channel and the skill is available.

## Operating principles

- **Faithful to the source, honest about limits.** Run all 7 steps, but never promise guaranteed results from a single tactic; the guarantee is in the weekly repetition.
- **Generate, don't just advise.** Every step should leave the user with concrete assets, not homework.
- **Manual steps are a feature.** Be explicit about what only the human can do, and make it a 30-second paste/click — never a vague "go do outreach."
- **Respect platform rules and the law.** No covert scrapers, no ToS-violating automation, no spam. Default to compliant, value-first tactics.

## Credit

Playbook adapted from [@fin465's thread](https://x.com/fin465/status/2066589201085370482) ("the YC playbook to brute-force your first 100 customers").
