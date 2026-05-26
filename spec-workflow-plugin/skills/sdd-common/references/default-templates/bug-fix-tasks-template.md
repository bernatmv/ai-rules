# Tasks Document

**Bug Spec:** fix-{slug}
**Originating Spec:** [spec-name or "N/A"]
**External Reference:** [JIRA/issue ID or "None"]

- [ ] 1. Apply fix in [file path]
  - File: [path/to/file.ts]
  - [Description of the code change]
  - Purpose: Resolve root cause of [bug summary]
  - _Leverage: [existing utilities or patterns to use]_
  - _Requirements: 1_
  - _Prompt: Role: [appropriate role] | Task: [specific fix description] | Restrictions: [do not change public API, maintain backward compat, etc.] | Success: [bug no longer reproduces, existing tests pass]_

- [ ] 2. Add regression tests in [test file path]
  - File: [tests/path/to/file.test.ts]
  - Write test(s) that reproduce the original bug scenario
  - Verify fix resolves the issue and adjacent paths are unaffected
  - Purpose: Prevent recurrence of this defect
  - _Leverage: [test utilities, fixtures]_
  - _Requirements: 1_
  - _Prompt: Role: QA Engineer | Task: Create regression tests that reproduce [bug scenario] and verify the fix | Restrictions: Must fail without the fix applied, must not depend on implementation details | Success: Tests pass with fix, fail without it, no flaky behavior_

- [ ] 3. Validate fix against reproduction steps
  - Execute reproduction steps from requirements.md — confirm bug no longer reproduces
  - Execute regression test(s) from task 2 — confirm they pass
  - Smoke-test regression scope items from design.md Fix Validation Plan
  - Confirm existing test suite passes
  - Purpose: End-to-end validation that the fix resolves the reported bug without side effects
  - _Requirements: 1_
  - _Prompt: Role: QA Engineer | Task: Validate fix by executing reproduction steps, regression tests, and smoke tests per the Fix Validation Plan in design.md | Restrictions: Do not modify any code; this is verification only | Success: Reproduction steps produce expected behavior, regression tests pass, smoke tests pass, full test suite green_

- [ ] 4. Update documentation (if applicable)
  - File: [docs/relevant-file.md or API docs]
  - Update any documentation affected by behavior changes
  - Purpose: Keep docs accurate after fix
  - _Requirements: 1_
