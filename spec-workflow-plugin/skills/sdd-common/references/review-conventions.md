# Review Conventions

Shared definitions for all SDD review skills.


## Contents

- [Severity & Scoring](#severity-scoring)
- [Standard Report Skeleton](#standard-report-skeleton)
- [Unified Finding Taxonomy](#unified-finding-taxonomy)
- [Advisory Rollup](#advisory-rollup)
- [Cross-Validation Score Modifier](#cross-validation-score-modifier)
- [After Review](#after-review)
- [Status Terminology](#status-terminology)
- [Sub-Agent Report — Two Statuses](#sub-agent-report--two-statuses)

## Severity & Scoring

**Severity:** 🔴 Critical (must fix) | 🟡 Warning (should fix) | 🟢 Suggestion (nice to have)

**Scoring:** ✅ Pass | ⚠️ Partial | ❌ Fail | ➖ N/A

**Status:** PASS (all ≥4/5, no critical) | NEEDS WORK (any =3/5) | FAIL (any ≤2/5) | INCOMPLETE (missing items)

## Standard Report Skeleton

All review reports follow this base structure. Skills add their specific sections
at the marked extension points.

1. **Header**: project/spec name, date, review scope
2. **Document Inventory / Workflow Status**: what was reviewed (✅/❌/⏭️)
3. **Overall Status**: PASS / NEEDS WORK / FAIL / INCOMPLETE
4. *[Skill-specific per-item analysis sections]*
5. **Summary Table**: scores at a glance
6. **Priority Fixes**: numbered list with severity icons (🔴 first, then 🟡, then 🟢)

## Unified Finding Taxonomy

Review artifacts carry a single `Finding` shape with a `source`
discriminator so per-facet issues, cross-validation findings, and
Tier 1 check advisories all flow through one counter. The post-review
envelope exposes `findings` as a nested dict keyed by `(source,
severity)`:

- `facet_issue` — per-facet issues (`critical | warning | suggestion`).
- `cross_validation` — cross-document findings
  (`duplication | conflict | gap | drift`).
- `tier1_check` — advisory signals
  (`template_compliance`, `size_check`, `cross_validation.status`).

Fix-loop routing uses the *actionable* subset —
`facet_issue.critical`, `facet_issue.warning`, and
`cross_validation.conflict`. Duplications, suggestions, and tier-1
advisories surface in the summary but do not route into the fix loop
by themselves (the advisory rollup downgrades `PASS` →
`PASS_WITH_ADVISORIES` instead).

## Advisory Rollup

Advisory signals never silently pass. When `template_compliance: FAIL`,
`size_check: WARNING`, or `cross_validation.status: NEEDS_WORK` is set
on a `PASS` artifact, `derive_overall_status` surfaces the signal by
returning `PASS_WITH_ADVISORIES`. New advisory signals register via
`@register_signal` in
`.cursor/skills/sdd-common/scripts/review_quality/signal_rollup.py` —
the rollup function never branches on signal name.

## Cross-Validation Score Modifier

When cross-validation findings exist at **warning** severity or higher, the overall
review score is capped at `max - 1.5` (one partial deduction). This ensures that
cross-document issues (DRY violations, inconsistencies between docs) are reflected
in the score even when individual per-document facets all pass.

**Rule:** If `cross_validation.status == NEEDS_WORK` and any finding has severity
≥ warning, apply `overall_score = min(overall_score, max_possible - 1.5)`.

## After Review

After any review, use `sdd-manage-status` to approve, reject, or request revision.
Each review skill's `validation-criteria.md` contains the detailed pass/fail criteria.

## Status Terminology

Two status systems are used across SDD skills:

### Spec Phase Status (from `spec-status` API)

| Status | Meaning |
|--------|---------|
| `created` | Document exists but is pending review (equivalent to `pending` in approvals) |
| `approved` | Document passed review |
| `missing` | Document does not exist yet |

### Approval JSON Status (from approval files)

| Status | Meaning |
|--------|---------|
| `pending` | Awaiting reviewer action (the spec-phase wire form is `created`; same state, different surface) |
| `approved` | Reviewer approved the document |
| `rejected` | Reviewer rejected the document |
| `needs_revision` | Reviewer requested changes |

## Sub-Agent Report — Two Statuses

Sub-agent review reports MUST keep the following two statuses
separate. Mixing them produces contradictions like "INCOMPLETE
because design.md and tasks.md do not yet exist" on a per-document
step that only examined ``requirements.md``, even though the
artifact score is PASS.

| Field | Meaning | Source of truth |
|-------|---------|-----------------|
| **Reviewed-docs status** | ``PASS`` / ``NEEDS_WORK`` / ``FAIL`` relative to the docs examined in *this* gate. | ``artifact_score.status`` on the post-review envelope. |
| **Artifact completeness** | ``INCOMPLETE`` whenever any document in ``documents_expected`` is missing from ``documents_reviewed``; ``PASS`` once every expected doc exists. | ``documents_reviewed`` vs ``documents_expected`` on the review-quality artifact. Informational only; never drives fix-loop routing. |

The ``post-review`` envelope emits a
``sub_agent_verdict_mismatch`` advisory whenever the prose report's
verdict line disagrees with the artifact score — e.g. prose says
``INCOMPLETE`` but the reviewed-docs score is ``PASS``. Consumers
treat the advisory as informational (the authoritative score wins)
but surface it so reviewers can update the prose.
