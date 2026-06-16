# First 100 Customers — Templates

All assets the skill generates. Fill the `{{placeholders}}` from the Growth Brief. Keep copies the user can edit; never invent facts about the product — pull them from the brief or ask.

---

## Growth Brief

Save to `first-100-customers/growth-brief.md` in the user's workspace.

```markdown
# Growth Brief — {{product_name}}

_Last updated: {{date}}_

## Product
- One-liner: {{what_it_does_in_one_sentence}}
- URL: {{product_url}}
- Pricing / free tier: {{pricing}}
- Open source: {{yes_no}}
- Demo asset (video/GIF): {{link_or_TODO}}

## Customer (ICP)
- Who: {{role_company_type}}
- Where they hang out: {{platforms_communities}}
- Top pain we solve: {{pain}}
- Qualify-in signals: {{signals}}
- Disqualifiers: {{disqualifiers}}

## Competitors / alternatives
1. {{competitor_1}} — {{domain}}
2. {{competitor_2}} — {{domain}}
3. {{competitor_3}} — {{domain}}

## Channels & assets we already have
- Building in public on: {{x_linkedin_other}}
- Follower counts / reach: {{reach}}

## Resources
- Weekly budget: {{budget}}
- Hours/week: {{hours}}

## Goal
- Current customers: {{current}}
- Target: {{target_default_100}}
- Deadline: {{deadline}}
```

---

## Weekly Tracker

Save to `first-100-customers/tracker.md`. Update after every step.

```markdown
# First 100 Customers — Tracker

**Customers: {{current}} / 100**  ·  Week of {{week_start}}

## This week's plan
- [ ] Step 1 Launch-max
- [ ] Step 2 Competitor backlinks
- [ ] Step 3 Warm outbound
- [ ] Step 4 UGC creators
- [ ] Step 5 Build-in-public video
- [ ] Step 6 Go where customers are
- [ ] Step 7 Ride weekly X trend

## Log
| Step | Action shipped | Result / metric | Date |
| ---- | -------------- | --------------- | ---- |

## Funnel snapshot
- Launches submitted: {{n}}
- Backlink emails sent / placements won: {{n}} / {{n}}
- Warm DMs sent / replies: {{n}} / {{n}}
- Creators signed / videos live: {{n}} / {{n}}
- Demo videos posted: {{n}}
- Shoutouts booked: {{n}}
- X posts/replies shipped: {{n}}
- **New customers this week: {{n}}**

## Next week
1. {{action}}
2. {{action}}
```

---

## Step 1 — Launch first comment (maker's intro)

```
Hey {{platform}} 👋 — I'm {{founder}}, maker of {{product_name}}.

{{one_liner}}. I built it because {{origin_pain}}.

What it does today:
• {{benefit_1}}
• {{benefit_2}}
• {{benefit_3}}

It's {{free_tier_or_pricing}}. I'd love your honest feedback — especially on {{thing_you_want_feedback_on}}. I'm here all day to answer questions.
```

**Show HN title:** `Show HN: {{product_name}} – {{what_it_does_in_plain_english}}`

---

## Step 2 — Backlink outreach email (to site owner)

```
Subject: A stronger {{category}} pick for {{their_article_title}}

Hi {{name}},

Your piece "{{article_title}}" is a great resource — I send people to it.

I run {{product_name}} ({{url}}), a {{category}} tool that {{differentiator_vs_listed_options}}. A few reasons it'd be a useful add for your readers:
• {{point_1}}
• {{point_2}}

Happy to send a short blurb + logo formatted however you like, or a free account so you can try it. Would you consider adding us to the list (or swapping in where {{competitor}} is)?

Thanks either way,
{{founder}} — {{url}}
```

**"Better version" outline (for your own page):** lead with the outcome the ICP wants → comparison table vs. {{competitor}} → proof (numbers, screenshots) → clear CTA. Aim to be objectively the most useful entry on the list.

---

## Step 3 — Warm outbound DM sequence

**ICP qualification rubric**
- Must-have: {{must_haves}}
- Nice-to-have: {{nice_to_haves}}
- Disqualify if: {{disqualifiers}}

**Touch 1 — connect / open (no pitch):**
```
Hey {{first_name}} — saw you {{engaged_with_specific_post}}. {{genuine_one_line_about_their_work}}. Following along!
```

**Touch 2 — value (1–2 days later):**
```
Since {{topic}} seems up your alley — we just {{relevant_resource_or_demo}}. Thought it might be useful: {{link}}. No ask, just sharing.
```

**Touch 3 — soft ask:**
```
Curious — how are you handling {{problem_product_solves}} today? We built {{product_name}} for exactly that; happy to show you in 5 min if it's relevant (totally fine if not).
```

---

## Step 3 — Warm outbound weekly prompt (reusable)

> Paste this each week with that week's list of people who engaged.

```
Here is this week's list of people who engaged with my posts: {{paste_handles_names_titles_links}}.

My ICP: {{icp_from_brief}}.

For each person:
1. Qualify against my ICP rubric (must-haves / disqualifiers) and label In / Maybe / Out with a one-line reason.
2. For everyone In (and Maybe), draft a personalized Touch-1 DM that references the specific post they engaged with — warm, human, no hard pitch.
Output a table: name · link · verdict · reason · drafted DM. I'll send them myself, spaced out.
```

---

## Step 4 — UGC creator brief / outreach / deal terms

**Creator brief**
```
Product: {{product_name}} — {{one_liner}}
Goal of the video: show {{use_case}} solving {{pain}} for {{audience}}
Hook ideas (first 2s): {{hook_1}} / {{hook_2}}
Must show: {{key_moment}}
Don'ts: {{donts}}
CTA: {{cta}}  ·  Link/code: {{link_or_promo}}
Deliverable: {{length}}s vertical video, posted from {{fresh_or_existing}} account, raw file sent to us
```

**Creator outreach DM**
```
Hi {{creator}} — love your content on {{niche}}. We're {{product_name}} and we'd love a short UGC video. Paid: ${{fixed_fee}} flat + performance bonuses (details below). Interested? I'll send a 1-page brief.
```

**Deal terms**
```
Fixed: ${{15_to_30}} per video on delivery.
Performance bonuses (cumulative):
• 100k views → ${{x}}
• 500k views → ${{y}}
• 1M views → $1,000
Usage: we may repost/boost the video. Payment via {{method}} on {{terms}}.
```

**Creator tracker table**
```
| Creator | Platform | Audience | Status (contacted/signed/live) | Fixed $ | Views | Bonus owed | Signups |
| ------- | -------- | -------- | ------------------------------ | ------- | ----- | ---------- | ------- |
```

---

## Step 5 — Demo video backlog & hooks

```
| # | Hook (first 2s) | Use case shown | CTA | Format (screen rec / talking head / b-roll) |
| - | --------------- | -------------- | --- | ------------------------------------------- |
```

**Hook formats that travel:** "POV: you {{painful_task}}…" · "I {{outcome}} in {{time}} — here's how" · "Stop doing {{old_way}}. Do this instead." · "Watch me {{do_the_thing}} in 30 seconds." Keep it under {{length}}s, show the product doing the work, end with the link.

---

## Step 6 — Community & shoutout pitch

**Sponsorship / shoutout pitch (newsletter, podcast, community owner)**
```
Hi {{name}} — your {{newsletter/podcast/community}} reaches exactly the people we build for ({{icp}}). We'd love a shoutout/sponsored mention of {{product_name}} ({{one_liner}}).

Can you share your sponsorship options + rates? Happy to give your audience an exclusive {{offer}} to make it worth their click.
```

**Value-first community intro (for no-promo communities)**
```
Hi all — {{founder}} here, working on {{space}}. Joined to learn from this group. Quick value: {{useful_tip_or_resource}}. Happy to help anyone with {{thing_you_know}} — reach out anytime.
```
> Contribute genuinely first; only mention the product when it's directly relevant or when the rules allow.

---

## Step 7 — X trend reply / QT / format

**Reply (add value, fold product in lightly):**
```
{{genuine_insight_or_addition_to_their_point}}. We see this a lot building {{product_name}} — {{specific_example}}. {{optional_link_if_natural}}
```

**Quote tweet (reuse their angle for your niche):**
```
{{their_claim}} is spot on. Here's how it plays out for {{your_niche}}: {{your_take}} 👇 {{mini_thread_or_demo}}
```

**Original post reusing a winning format:** take the structure of the viral post (hook → list → payoff) and rebuild it with your product's story. Lead with the outcome; make the format do the work.
