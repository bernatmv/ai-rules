# Bug Fix Spec Criteria

Loaded when spec is detected as a bug fix per `$SKILLS/sdd-common/references/detection-rules.md`.

## Contents
- [Additional requirements.md Criteria](#additional-requirementsmd-criteria)
  - [Technical Context Documents Issues](#1-technical-context-documents-issues-covers-bug-summary-environmentcontext-currentexpected-behavior-reproduction-steps-traceability)
  - [Reproduction Steps Actionable](#1b-reproduction-steps-actionable-covers-reproduction-steps-quality)
  - [Issue Scope Bounded](#2-issue-scope-bounded-covers-scope-boundary-severityimpact)
- [Additional design.md Criteria](#additional-designmd-criteria)
  - [Root Cause Analysis Present](#1-root-cause-analysis-present-covers-root-cause-analysis-how-bug-was-introduced-originating-spec-reference)
  - [Solution Addresses Root Cause](#2-solution-addresses-root-cause-covers-fix-approach-rejected-alternatives)
  - [Regression Risk Assessed](#3-regression-risk-assessed-covers-regression-risk-assessment-regression-test-strategy)
  - [Fix Validation Plan Present](#4-fix-validation-plan-present-covers-fix-validation-plan)

## Additional requirements.md Criteria

### 1. Technical Context Documents Issues (covers: Bug Summary, Environment/Context, Current/Expected Behavior, Reproduction Steps, Traceability)

**Pass:**
- Current broken behavior described
- Steps to reproduce implicit/explicit
- Affected components identified
- Severity/impact stated
- Traceability section present — originating spec documented or explicitly "N/A"

**Fail:**
- Jumps into fix without describing broken behavior
- Affected components unclear
- Missing severity assessment
- Traceability section entirely missing

### 1b. Reproduction Steps Actionable (covers: Reproduction Steps quality)

**Pass:**
- Each step is a concrete action (not "do the thing that causes it")
- Preconditions/setup explicitly stated (environment, data, user state)
- Expected result at the failing step clearly stated (what you see vs what you should see)
- Steps are independently executable — a developer unfamiliar with the bug can follow them
- Environment/platform specifics noted if relevant

**Fail:**
- Steps are vague or assume insider knowledge ("reproduce the issue")
- Missing preconditions — cannot set up the scenario from the steps alone
- No expected vs actual at the failing step
- Steps require running the full app with no guidance on where to look

### 2. Issue Scope Bounded (covers: Scope Boundary, Severity/Impact)

**Pass:**
- Clear broken vs working distinction
- Fix limited to identified issues
- No scope creep into enhancements
- Regression risks acknowledged

**Fail:**
- Scope unclear or unbounded
- Enhancement mixed with fix
- Regression risks ignored

## Additional design.md Criteria

### 1. Root Cause Analysis Present (covers: Root Cause Analysis, How Bug Was Introduced, Originating Spec Reference)

**Pass:**
- Root cause identified (not symptoms)
- Code-level explanation
- References to specific files/functions
- How bug was introduced (if known)
- If bug was introduced by a prior spec, originating spec name and requirement/task ID documented; if not related to any spec, explicitly states "N/A" with brief origin context

**Fail:**
- Only symptoms described
- No code-level detail
- Missing file/function references
- Bug clearly traces to a prior spec but no cross-reference provided

### 2. Solution Addresses Root Cause (covers: Fix Approach, Rejected Alternatives)

**Pass:**
- Fix directly addresses cause
- Not a workaround/band-aid
- Explains why fix resolves issue
- Considers other potential issues

**Fail:**
- Workaround instead of fix
- Doesn't explain resolution
- Ignores related issues

### 3. Regression Risk Assessed (covers: Regression Risk Assessment, Regression Test Strategy)

**Pass:**
- Affected code areas identified
- Potential regression scenarios listed
- Testing strategy for regressions
- Backward compatibility documented

**Fail:**
- No regression analysis
- Missing test strategy for regressions
- Backward compatibility unconsidered

### 4. Fix Validation Plan Present (covers: Fix Validation Plan)

**Pass:**
- Pre-fix reproduction baseline documented (confirms bug exists before fix)
- Post-fix verification steps mapped to reproduction steps from requirements.md
- Regression scope identifies adjacent features to smoke-test
- At least one automated regression test encodes the reproduction-to-verification cycle

**Fail:**
- No validation plan — document assumes fix will work without verification protocol
- Post-fix verification not linked to reproduction steps
- No mention of pre-fix baseline confirmation
