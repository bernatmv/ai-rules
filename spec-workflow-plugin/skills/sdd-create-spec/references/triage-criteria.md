# Bug Fix Triage Criteria

Classify severity before starting the bug fix workflow. Severity determines routing (fast path vs standard) and document depth.

## Severity Levels

> **Legend (Bug Triage):** 🔴 Critical | 🟡 High | 🟠 Medium | 🔵 Low

| Severity | Definition | Examples |
|----------|-----------|----------|
| 🔴 Critical | System down, data loss/corruption, security vulnerability, no workaround | Production crash, auth bypass, data deletion bug |
| 🟡 High | Major feature broken, workaround exists but is painful | Payment flow fails on retry, search returns wrong results |
| 🟠 Medium | Minor feature broken, low user impact, easy workaround | Sorting ignores locale, tooltip shows stale data |
| 🔵 Low | Cosmetic, rare edge case, minor inconvenience | Misaligned icon, off-by-one in pagination edge case |

## Workflow Routing

| Severity | Document Flow | Approval Strategy | Task Count |
|----------|--------------|-------------------|------------|
| 🔴 Critical | Fast path | Combined requirements + design review | 2 (fix + test) |
| 🟡 High | Fast path (user choice) | Combined or sequential | 2-3 |
| 🟠 Medium | Standard 3-doc flow | Sequential approval per doc | 2-4 |
| 🔵 Low | Standard 3-doc flow | Sequential approval per doc | 2-4 |

## Classification Guidance

**Ask these questions to determine severity:**

1. **Is the system unusable or data at risk?** → Critical
2. **Is a major feature broken with no reasonable workaround?** → High
3. **Is functionality impaired but users can work around it?** → Medium
4. **Is the issue cosmetic or extremely rare?** → Low

**When ambiguous:** Default to the higher severity and let the user confirm or downgrade during triage.

## Fast Path Rules

Fast path (Critical/High) modifies the standard workflow:

- **Combined review**: requirements.md and design.md presented together for a single approval pass
- **Minimal tasks**: Only fix + regression test (skip optional documentation task)
- **Urgency flag**: Note severity prominently in the spec header so reviewers prioritize

The user must explicitly confirm fast path routing. Never auto-escalate to fast path.
