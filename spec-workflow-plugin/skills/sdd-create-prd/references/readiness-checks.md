# Readiness Checks

Each gate runs in two layers:
1. **Script check** (`validate-readiness.py`) — structural, deterministic
2. **Judgment check** — AI-assessed quality criteria

**Max retries:** If a gate's script check fails after 2 write-and-revalidate cycles, stop looping — surface all remaining gaps to the PM and ask them to provide the missing information directly.

## Pre-Requirements Gate (after Step 3, before Step 4)

### Script check
```bash
.spec-workflow/sdd prd/validate-readiness.py --target "{feature-name}" --gate pre-requirements --session-file
```
Exit 0 = pass. Exit 1 = gaps (JSON lists missing items).

The `--session-file` flag tells the script to read `.prd-session.json` (written
progressively during Steps 1-3) instead of the full PRD document (which
does not exist yet at this point in the workflow).

> **Two input modes:** The script accepts either a full PRD document
> (default, used in update mode and post-generation re-validation) or
> a session state file (`--session-file`, used during the conversational
> creation flow before Step 6).

Script validates:
- Problem statement section exists and has 2+ non-empty sentences
- At least 2 goals with non-placeholder Metric + Target + Measurement Method columns
- Non-goals section exists with at least 1 entry that has a Reason column

### Judgment check (after script passes)

**Problem Readiness:**
- [ ] Problem names a specific persona, not a generic user
- [ ] The cost/pain is concrete (quantified or described in user terms)
- [ ] "Why now" is articulated — not just "it would be nice"
- [ ] No solution is named in the problem statement

**Goals Readiness:**
- [ ] Metrics are attributable to this feature (not vanity)
- [ ] Measurement method is feasible (data source exists)

**Scope Readiness:**
- [ ] Ambiguous items resolved or explicitly deferred to open questions
- [ ] Non-goal reasons are substantive, not just "out of scope"

### Anti-Confabulation Check
- [ ] All content in the current draft originates from PM conversation or steering docs
- [ ] No sections were auto-filled by the agent without PM input
- [ ] Open questions are recorded, not resolved by the agent

If ANY dimension is weak, surface it and resolve before Step 4.

## Pre-Generation Gate (after Step 5, before Step 6)

### Script check
```bash
.spec-workflow/sdd prd/validate-readiness.py --target "{feature-name}" --gate pre-generation --session-file
```

Script validates (builds on pre-requirements checks):
- All P0 requirements contain WHEN/THEN pattern
- Each WHEN/THEN has a named subject in the THEN clause
- All 6 NFR subsections (Performance, Availability, Scalability, Security, Data Consistency, Observability) present and non-placeholder
- No NFR marked TBD without a subsequent "Owner:" and "Due:" annotation
- Open questions table entries have Owner + Due Date + Blocks columns

### Judgment check (after script passes)

- [ ] No red flags from RYG assessment, OR explicit decision to proceed
- [ ] Engineer pushback objections addressed or documented as open questions
- [ ] NFR values are specific enough to implement against (not adjectives)
- [ ] Financially material data → idempotency requirement is present

### Anti-Confabulation Check
- [ ] All content in the current draft originates from PM conversation or steering docs
- [ ] No sections were auto-filled by the agent without PM input
- [ ] Open questions are recorded, not resolved by the agent

