# Stress Test Protocol

## 5a: Engineer Pushback Simulation

Adopt the persona of a senior engineer reviewing this PRD, but
**ground every objection in one of**:
- A specific requirement or NFR from this PRD
- A constraint from the steering doc (product.md / tech.md)
- A gap between what the PM said and what the PRD states
- An explicit open question that blocks implementation

**Do NOT** raise concerns based on general engineering best practices
unless they directly contradict something in the project context.
If a concern is speculative, present it as a question to the PM,
not as an objection.

Surface 5 pointed objections covering:
- Ambiguities that force product decisions during implementation
- Missing edge cases and failure modes
- Product decisions left to engineering judgment
- NFRs too vague to implement against
- Open questions that block implementation

For each objection:
1. State the concern clearly
2. Reference the specific PRD section
3. Ask the PM to resolve or document as open question

## 5b: Red-Yellow-Green Assessment

Assess each dimension:

| Dimension | Green | Yellow | Red |
|-----------|-------|--------|-----|
| Problem statement | Sharp, specific, no solution | Minor clarity issues | Solution-as-problem or vague |
| Goals | Measurable, attributable | Measurement method unclear | Vanity metrics or unmeasurable |
| Requirements | Complete, testable WHEN/THEN | Minor gaps | Major missing cases |
| NFRs | Specific values per category | 1-2 categories weak | Blanks or TBD without plan |
| Open questions | All have owners + Blocks | Some missing owners | Blockers without owners |
| Rollout plan | Stages with gates + rollback | Missing rollback for some | No phased plan |

Action: Flag anything Red. User must fix Red items or explicitly
document them as accepted risk before proceeding to Step 6.
