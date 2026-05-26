# PRD Anti-Patterns

Detection table for common PRD failure modes. Each anti-pattern maps
to a template section and has a detection heuristic.

| Anti-Pattern | Section | Detection Signal | Severity |
|-------------|---------|------------------|----------|
| Solution-as-Problem | 1. Problem Statement | Problem statement names a technology, architecture, or specific implementation | Critical |
| Orphaned PRD | Metadata | No Related PRDs links when prior PRDs exist in specs/ | Major |
| Vanity Goal | 3. Goals | Metric would move regardless of this feature; no attribution method | Critical |
| Unstated Reason Non-Goal | 4. Non-Goals | Non-goal entry has no Reason column or reason is blank | Major |
| Homeless Persona | 5a. Personas | Persona not referenced in steering product.md | Minor |
| Wishlist Story | 5b. User Stories | User story has no WHEN/THEN acceptance criterion | Major |
| Capability Requirement | 6. Requirements | "System can X" instead of "WHEN Y THEN system SHALL X" | Major |
| Unnamed Subject | 6. Requirements | THEN clause says "SHALL" without naming which system/component | Major |
| NFR-less PRD | 6b. NFRs | One or more of the 6 categories blank or TBD without resolution plan | Critical |
| Vague NFR | 6b. NFRs | NFR uses adjectives ("fast", "secure", "scalable") instead of values | Major |
| Undebated Decision | 7. Alternatives | Section empty or contains only the chosen approach | Major |
| Big-Bang Launch | 8. Rollout | No phases, or phases without success gates or rollback plans | Major |
| Parking Lot Question | 9. Open Questions | Entry missing Owner, Due Date, or Blocks column | Major |
| Implicit Assumption | 11. Appendix | Assumptions list empty when PRD references external systems | Minor |

## Why This Matters for SDD

Each section of the PRD template maps to something an implementation
agent needs:
- Problem Statement → the "why" that anchors every trade-off
- WHEN/THEN Requirements → directly executable as test cases
- NFRs → implementation constraints designed in, not bolted on
- Alternatives Considered → explicit anti-patterns ("don't do X because Y")
- Phase Boundaries → scope constraints that prevent over-engineering
