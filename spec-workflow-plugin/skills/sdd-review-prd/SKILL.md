---
name: sdd-review-prd
description: Reviews PRD document quality for problem clarity, goal measurability,
  requirement testability, NFR completeness, and SDD readiness. Use when asked to
  review a PRD, validate a PRD, check PRD quality, or assess PRD readiness.
allowed-tools: Read Write Edit Bash Agent AskQuestion AskUserQuestion TaskCreate TaskUpdate WebFetch
metadata:
  version: 3.3.1
  category: review
  dependencies: [sdd-common]
  author: membership-platforms-sdd-guild
---

> **Paths:** See `$SKILLS/sdd-common/references/path-conventions.md`. Scripts: `.spec-workflow/sdd {group}/{script}.py`.

# SDD: Review PRD

Reviews PRD documents against quality criteria. Validates problem clarity,
goal measurability, requirement completeness, NFR specificity, and
cross-document consistency with steering docs.

Severity, scoring, and report conventions: see
`$SKILLS/sdd-common/references/review-conventions.md`.

## Contents

- [Dependencies](#dependencies)
- [Invocation Examples](#invocation-examples)
- [Pre-Review: Steering Doc Check](#pre-review-steering-doc-check)
- [Parameters](#parameters)
- [Workflow](#workflow)
- [Workflow Progress](#workflow-progress)
- [Safety Rules](#safety-rules)
- [Edge Cases](#edge-cases)
- [Human approval ceremony](#human-approval-ceremony)
- [Completion](#completion)
- [Reference Files](#reference-files)

## Dependencies

> **Load on demand**: Read each file only when the workflow reaches that step — not all upfront.

| Step | File | Kind | Freedom |
|------|------|------|:-:|
| Steps 1–4 | `$SKILLS/sdd-common/references/review-workflow-base.md` (shared workflow skeleton) | read | L |
| Step 1 | `$SKILLS/sdd-common/references/tool-patterns.md` (spec discovery via scripts) | read | L |
| Step 5 | `$SKILLS/sdd-review-prd/references/validation-criteria-prd.md` | read | M |
| Step 5.1 | `$SKILLS/sdd-common/references/template-compliance.md` | read | M |
| Step 5.2 | `$SKILLS/sdd-review-prd/references/prd-anti-patterns.md` | read | M |
| Step 5.3 | `$SKILLS/sdd-review-prd/references/cross-validation-criteria.md` | read | M |
| Step 5.4 | `$SKILLS/sdd-common/scripts/prd/validate-prd.py` (tier 1 deterministic) | run | L |
| Step 7 | `$SKILLS/sdd-common/references/review-conventions.md` (report skeleton) | read | L |
| Step 7.1 | `$SKILLS/sdd-common/references/quality-artifact-base.md` (shared envelope, scores, conventions) | read | L |
| Step 7.1 | `$SKILLS/sdd-review-prd/references/artifact-assessment-format.md` | read | M |

## Invocation Examples

| Request | Action |
|---------|--------|
| "sdd review prd [feature-name]" | Review default `prd.md` or prompt if multiple PRDs exist |
| "sdd review prd [feature-name] [prd-name]" | Review specific PRD |
| "sdd review prd [feature-name] --all" | Review all PRDs in discovery project sequentially |
| "sdd review prd [feature-name] --with-steering" | Review with steering doc cross-validation |

## Pre-Review: Steering Doc Check

Before reviewing PRD, verify steering docs exist. If product.md is
missing, flag a `⚠️ Steering Doc Warning` — PRD may be context-free.

## Parameters

| Parameter | Value |
|-----------|-------|
| DISCOVERY_TOOL | `discovery/validate-manifest.py` (manifest-based; **not** `spec/check-status.py`) |
| DOCUMENT_LIST | `{prd-name}` — specified PRD, or auto-discovered via manifest |
| LOCATE_STRATEGY | Manifest artifacts (`type: "prd"`) → fallback glob `prd*.md`. See Step 2 for full workflow. |
| CRITERIA_MAPPING | {prd-name} → `references/validation-criteria-prd.md` |
| CROSS_VALIDATION_PAIRS | prd↔product.md (steering) |

## Workflow

### Steps 1–5.1: Discovery, Scope, Checklists, Template Compliance

**1. Discover** — Read manifest at `.spec-workflow/discovery/{feature-name}/manifest.json`.
If manifest missing, run: `.spec-workflow/sdd discovery/validate-manifest.py --name "{feature-name}"`.

Do **not** use `spec/check-status.py` for PRD discovery — it only searches `.spec-workflow/specs/`.

**2. Locate & Select PRD**

1. Read manifest at `.spec-workflow/discovery/{feature-name}/manifest.json`
2. Filter artifacts where `type == "prd"` → PRD list
3. Fallback: if manifest missing/corrupt, glob `prd*.md` in project folder

Selection rules:
- User specified `[prd-name]` → review that file
- Exactly one PRD, no name given → use it
- Multiple PRDs, no name given → list, prompt user to choose
- `--all` flag → review all sequentially, one report per PRD

Errors:
- Zero PRDs → "No PRDs found. Create one with `sdd create prd {feature-name}`."
- Specified PRD not on disk → "File not found. Re-register with `sdd discovery add`."

**3. Status** — Check pending approvals per `$SKILLS/sdd-common/references/approval-flow.md`
**4. Scope** — Single document review ({prd-name} only)
**5. Checklists** — Load per-section criteria from CRITERIA_MAPPING
**5.1. Template Compliance** — Run compliance check per `$SKILLS/sdd-common/references/template-compliance.md`

For detailed procedures, see `$SKILLS/sdd-common/references/review-workflow-base.md` Base Steps A–F.

### Step 5.2: Anti-Pattern Detection

Read `references/prd-anti-patterns.md` and scan the PRD for each
anti-pattern. Score presence/absence. Key anti-patterns:
- Solution-as-problem (Section 1)
- Vanity metrics (Section 3)
- Homeless persona (Section 5a)
- Capability requirement vs WHEN/THEN (Section 6)
- NFR-less PRD / vague NFR (Section 6b)
- Undebated decision (Section 7)
- Parking lot open question (Section 9)

### Step 5.3: Cross-Document Validation

Follow **Base Step G** from `$SKILLS/sdd-common/references/review-workflow-base.md`.
Cross-validate PRD against steering product.md for:
- Persona consistency
- Goal alignment with product vision
- Constraint compatibility

### Step 5.4: Tier 1 Deterministic Checks

Run the following script. Its per-check JSON output is the **authoritative score**
for structural facets — do not override via AI judgment:

| Script | Document | Authoritative facets |
|--------|----------|---------------------|
| `.spec-workflow/sdd prd/validate-prd.py {prd-name}` | {prd-name} | `requirements_when_then_format`, `nfrs_all_categories_specific`, `open_questions_have_owners`, `alternatives_considered_present`, `rollout_plan_with_gates`, `goals_table_complete` |

Run the script and record per-facet results from the JSON output `data.checks`:
- Each check ID maps to `pass` or `fail` independently

These Tier 1 facet IDs must **not** appear in the `tier2_scores` block in Step 7.1.
See `references/artifact-assessment-format.md` § Document Keys and Facet Ownership for the full split.

### Step 6: SDD Readiness Assessment

| Question |
|----------|
| Can each WHEN/THEN requirement be directly converted to a test case? |
| Are NFRs specific enough to constrain architecture decisions? |
| Do alternatives considered provide explicit anti-patterns for a coding agent? |
| Are phase boundaries clear enough to scope implementation tasks? |

### Step 7: Generate Report

Follow **Base Step H** from `$SKILLS/sdd-common/references/review-workflow-base.md`.

1. **Per-Section**: score, checklist results, issues found
2. **Anti-Pattern Summary**: detected anti-patterns with severity
3. **Cross-Validation**: consistency with steering docs
4. **SDD Readiness**: confidence level for spec-driven development
5. **Tier 1 Results**: validate-prd.py outcomes (authoritative)

### Step 7.1: Write Quality Artifact

Read `references/artifact-assessment-format.md` for the exact JSON format
(Tier 2 only — Tier 1 facets are script-determined), exclusion list, and run command.

## Workflow Progress

Copy this checklist and track progress:

```
PRD Review Progress:
- [ ] Pre-check: Verify steering docs exist (flag warning if missing)
- [ ] Step 1: Discover project folder and identify PRD(s) — Triage: T0
- [ ] Step 2: Locate & select PRD from manifest
- [ ] Step 3: Check pending approvals
- [ ] Step 4: Scope — single document review
- [ ] Step 5: Apply per-section checklists (validation-criteria-prd.md)
- [ ] Step 5.1: Template compliance check (via sdd-common)
- [ ] Step 5.2: Anti-pattern detection (prd-anti-patterns.md)
- [ ] Step 5.3: Cross-document validation with steering docs
- [ ] Step 5.4: Run `.spec-workflow/sdd prd/validate-prd.py` for Tier 1 deterministic checks
- [ ] Step 6: SDD readiness assessment
- [ ] Step 7: Generate review report with scores
- [ ] Step 7.1: Run `.spec-workflow/sdd review/update-quality.py` to write quality artifact
```

## Safety Rules

See `$SKILLS/sdd-common/references/review-safety-rules.md` for shared rules.

## Edge Cases

- If a document section is empty, score it as INCOMPLETE rather than FAIL
- If template compliance check fails, still complete the full review
- If steering docs are missing, flag warning and proceed without cross-validation

## Human approval ceremony

Follow [`human-approval-ceremony.md`]($SKILLS/sdd-common/references/human-approval-ceremony.md) with `target_label="{prd-name}"` before any `.spec-workflow/sdd approval/update-status.py … approve`.

## Completion

Follow **Base Step I** from `$SKILLS/sdd-common/references/review-workflow-base.md`.

PRD review complete. To approve, run `sdd approve prd {feature-name}`. To request revision, ask for changes.

## Reference Files

- `references/validation-criteria-prd.md` — Per-section validation criteria for PRD review
- `references/prd-anti-patterns.md` — Common PRD anti-patterns to detect
- `references/cross-validation-criteria.md` — Cross-document consistency checks (PRD ↔ steering)
- `references/artifact-assessment-format.md` — Quality artifact JSON format for review output
