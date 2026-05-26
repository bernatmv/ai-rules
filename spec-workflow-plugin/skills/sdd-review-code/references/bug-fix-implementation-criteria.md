# Bug Fix Implementation Review Criteria

Loaded alongside the per-dimension criteria files when reviewing implementations of bug fix specs per `$SKILLS/sdd-common/references/detection-rules.md`.

These criteria supplement — not replace — the standard review dimensions. Apply both this file and the dimension criteria files for a complete bug fix implementation review.

## Contents
- [Fix Addresses Root Cause](#1-fix-addresses-root-cause-not-symptoms)
- [Regression Test Reproduces Original Bug](#2-regression-test-reproduces-original-bug)
- [Fix Validated Against Reproduction Steps](#2b-fix-validated-against-reproduction-steps)
- [Scope Contained](#3-scope-contained)
- [No New Issues Introduced](#4-no-new-issues-introduced)
- [Existing Tests Still Pass](#5-existing-tests-still-pass)
- [Summary Table](#summary-table)

---

## 1. Fix Addresses Root Cause (not symptoms)

**Pass:**
- Code change directly matches the root cause identified in design.md "Root Cause Analysis"
- The defect mechanism described in design.md is eliminated by the change
- Fix does not merely suppress error messages or mask incorrect behavior

**Fail:**
- Fix is a workaround or band-aid (e.g., catching and swallowing errors, adding null checks around symptoms)
- Code change targets a different location than identified in design.md
- Root cause remains present; fix only hides observable symptoms

---

## 2. Regression Test Reproduces Original Bug

**Pass:**
- At least one test exists that exercises the exact reproduction path from requirements.md
- Test fails without the fix applied and passes with it (verified by reasoning about test logic or temporary revert)
- Test assertions target the specific broken behavior, not just general correctness

**Fail:**
- Test only checks new/changed behavior without reproducing the original bug scenario
- Test would pass even without the fix (does not actually guard against regression)
- No test directly tied to the reproduction steps in requirements.md

---

## 2b. Fix Validated Against Reproduction Steps

**Pass:**
- Evidence that reproduction steps from requirements.md were executed post-fix
- Reproduction steps now produce expected behavior (not the broken state)
- Validation covers both automated (regression test) and manual/smoke test paths from the Fix Validation Plan
- If fast path: task 2 success criteria explicitly confirm reproduction step resolution

**Fail:**
- No evidence of post-fix reproduction step execution
- Only automated tests run; no confirmation that the user-facing reproduction path is resolved
- Validation Plan items from design.md not addressed

---

## 3. Scope Contained

**Pass:**
- Changes are limited to files listed in requirements.md "Affected Components"
- Any changes outside the identified scope have explicit justification (e.g., shared utility needed by the fix)
- No opportunistic refactoring, feature additions, or unrelated cleanups bundled with the fix

**Fail:**
- Changes spread to files not identified in requirements.md without justification
- Fix includes enhancements or refactoring beyond what is needed for the defect
- Scope boundary from requirements.md violated

---

## 4. No New Issues Introduced

**Pass:**
- Fix does not create new edge cases or failure modes
- Adjacent code paths and shared data structures remain correct
- Error handling for the fixed path is complete (no new unhandled states)

**Fail:**
- Fix resolves one issue but introduces a new defect or edge case
- Shared state or data structures are left in an inconsistent state for other callers
- New code paths lack error handling

---

## 5. Existing Tests Still Pass

**Pass:**
- Full test suite runs green after the fix
- No existing tests were modified to accommodate the fix (unless the test itself was testing incorrect behavior)
- CI/build pipelines pass

**Fail:**
- Existing tests broken by the fix
- Tests modified to "make them pass" without clear justification that the old assertion was wrong
- Build or lint failures introduced

---

## Summary Table

| # | Criterion | Pass | Fail |
|---|-----------|------|------|
| 1 | Fix addresses root cause | Code change matches design.md root cause analysis | Fix is a workaround or band-aid |
| 2 | Regression test reproduces original bug | Test fails without fix, passes with it | Test only checks new behavior |
| 2b | Fix validated against reproduction steps | Reproduction steps executed post-fix, expected behavior confirmed | No evidence of post-fix reproduction validation |
| 3 | Scope contained | Changes limited to affected components | Changes spread beyond identified scope |
| 4 | No new issues introduced | Fix doesn't create new edge cases | Fix solves one issue but introduces another |
| 5 | Existing tests still pass | Full test suite green | Existing tests broken by fix |

---

**Referenced by:** `sdd-create-spec/SKILL.md` (bug-fix mode handoff) and `sdd-review-code/SKILL.md` when reviewing bug fix implementations.
