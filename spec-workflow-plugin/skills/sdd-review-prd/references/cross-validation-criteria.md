# PRD Cross-Validation Criteria

Cross-validate PRD against steering docs when `--with-steering` is specified
or when steering docs are available.

## PRD ↔ product.md

| Check | Pass | Fail |
|-------|------|------|
| Persona consistency | PRD personas match or extend product.md personas | PRD introduces personas not in product.md without explanation |
| Goal alignment | PRD goals support product vision and business objectives | PRD goals contradict or are unrelated to product vision |
| Constraint compatibility | PRD NFRs are compatible with product.md constraints | PRD NFRs weaken or contradict product-level requirements |
| Feature scope | PRD scope aligns with product roadmap context | PRD scope extends beyond stated product boundaries |

## PRD ↔ tech.md

| Check | Pass | Fail |
|-------|------|------|
| Technology assumptions | PRD NFRs are achievable with current tech stack | PRD assumes technology not in tech.md |
| Architecture compatibility | PRD requirements are implementable within current architecture | PRD implies architectural changes not acknowledged |
| Performance targets | PRD targets are within tech.md's stated bounds | PRD targets exceed infrastructure capabilities |

## PRD ↔ structure.md

| Check | Pass | Fail |
|-------|------|------|
| Module boundaries | PRD functional requirements map to existing module structure | PRD implies new modules not noted |
| Naming conventions | PRD terminology aligns with codebase naming | PRD introduces terminology inconsistent with structure.md |

## Findings Format

For each conflict, gap, or inconsistency found, produce a one-sentence
`summary` (max ~200 chars) explaining the issue. Include as `findings`
in the assessment JSON.
