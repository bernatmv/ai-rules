# Test Cases

Triggering, functional, and regression test cases for SDD skills.

## Contents
- [Triggering Tests](#triggering-tests)
- [Functional Tests](#functional-tests)
- [Regression Tests](#regression-tests)

## Triggering Tests

### sdd-create-spec (bug-fix mode)

**Should trigger:**
- "sdd bug fix login timeout"
- "sdd hotfix auth failing"

**Should NOT trigger:**
- "fix my code formatting" (not a spec request)
- "what does sdd create spec do?" (informational)
- "review the fix-login spec" (triggers review, not create-spec)

### sdd-manage-status

**Should trigger:**
- "sdd approve spec user-auth"
- "sdd approve steering"
- "sdd reject user-auth design.md"
- "sdd request revision user-auth"
- "sdd list pending"

**Should NOT trigger:**
- "what's the status of my spec?" (informational — use sdd-manage-status)
- "approve this PR" (not SDD related)

### sdd-review-code

**Should trigger:**
- "sdd review code"
- "sdd review changes"
- "sdd review implementation user-auth"
- "sdd review task 2.1 user-auth"
- "sdd review PR"
- "run code review"

**Should NOT trigger:**
- "review the spec documents" (triggers spec review)
- "implement task 2" (implementation, not review)

### sdd-review-spec-docs

**Should trigger:**
- "sdd review spec user-auth"
- "sdd review spec user-auth design.md"
- "sdd review all specs"

**Should NOT trigger:**
- "review steering docs" (triggers steering review)
- "create a spec" (triggers create-spec, not review)

### sdd-review-steering-docs

**Should trigger:**
- "sdd review steering"
- "sdd review steering tech.md"
- "sdd detect drift"

**Should NOT trigger:**
- "review spec documents" (triggers spec review)
- "update my tech.md" (editing, not review)

## Functional Tests

### Bug Fix Detection

| Spec Name | Expected | Reason |
|-----------|----------|--------|
| `fix-login-timeout` | ✅ Bug fix | Contains `fix` |
| `hotfix-payment` | ✅ Bug fix | Contains `hotfix` |
| `bugfix-search-null` | ✅ Bug fix | Contains `bugfix` |
| `patch-edge-case` | ✅ Bug fix | Contains `patch` |
| `issue-auth-failure` | ✅ Bug fix | Contains `issue` |
| `user-auth` | ❌ Not bug fix | No keywords |
| `fixture-setup` | ❌ Not bug fix | `fixture` ≠ `fix` (word-boundary aware) |
| `prefix-suffix` | ❌ Not bug fix | `fix` substring of `prefix`/`suffix` |

### Approval Status Transitions

| Current Status | Action | Expected Result |
|---------------|--------|----------------|
| `pending` | approve | ✅ Changes to `approved` |
| `pending` | reject | ✅ Changes to `rejected` |
| `pending` | needs_revision | ✅ Changes to `needs_revision` |
| `approved` | approve | ⚠️ Skip with warning |
| `approved` | reject | ⚠️ Skip unless user overrides |
| `rejected` | approve | ⚠️ Skip unless user overrides |

## Regression Tests

| Scenario | Expected Behavior | Skill |
|----------|------------------|-------|
| `fixture-setup` spec name | NOT detected as bug fix | detection-rules |
| Empty approval JSON (0 bytes) | Warn and skip, don't crash | manage-status |
| Missing `.spec-workflow/` directory | Create or guide, don't crash | all skills |
| Spec with only requirements.md | Review available docs, note gaps | spec review |
| Steering doc > 300 lines | Flag as fail (not just warning) | steering review |
| All spec phases `missing` | Report and guide to creation | impl review |
| Malformed JSON in approval file | Warn with file path, skip | manage-status |
