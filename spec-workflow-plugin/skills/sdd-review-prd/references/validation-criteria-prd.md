# PRD Validation Criteria

Criteria marked (T1) = Tier 1 deterministic (script-verified, authoritative).
Criteria marked (T2) = Tier 2 AI-assessed.

## Section 1: Problem Statement
- [ ] (T2) 2-4 sentences, no solution named
- [ ] (T2) Persona identified
- [ ] (T2) Cost/impact quantified
- [ ] (T2) "Why now" articulated

## Section 2: Background and Context
- [ ] (T2) References steering doc (not duplicates it)
- [ ] (T2) Feature-specific context only

## Section 3: Goals
- [ ] (T1) 2+ goals with non-placeholder Metric + Target + Measurement columns
- [ ] (T2) Metrics are attributable to this feature (not vanity)

## Section 4: Non-Goals
- [ ] (T1) Each entry has a non-empty Reason column
- [ ] (T2) Reasons are substantive, not just "out of scope"

## Section 5a: Personas
- [ ] (T2) Named personas with goal and pain
- [ ] (T2) References steering doc personas (not reinvented)

## Section 5b: User Stories
- [ ] (T1) Acceptance criteria contain WHEN/THEN pattern
- [ ] (T2) WHEN/THEN is behavioral, not capability-style

## Section 6: Functional Requirements
- [ ] (T1) WHEN/THEN format present in requirement entries
- [ ] (T1) THEN clause contains a named subject
- [ ] (T2) Edge cases and failure modes specified

## Section 6b: NFRs
- [ ] (T1) All 6 categories present (Performance, Availability, Scalability,
       Security, Data Consistency, Observability)
- [ ] (T1) No category is placeholder-only text
- [ ] (T2) Values are specific enough to implement against
- [ ] (T2) Financially material data → idempotency required

## Section 7: Alternatives Considered
- [ ] (T1) Section non-empty, at least one table entry
- [ ] (T2) Each has a substantive reason for rejection

## Section 8: Phased Rollout
- [ ] (T1) Table has Success Gate + Rollback Plan columns
- [ ] (T2) Success gates are measurable

## Section 9: Open Questions
- [ ] (T1) Each entry has Owner + Due Date + Blocks columns
- [ ] (T2) Blocks entries correctly identify dependent work

## Section 10: Out of Scope
- [ ] (T2) Deferred items with rationale
- [ ] (T2) Future PRD candidates noted

## Section 11: Appendix
- [ ] (T2) Assumptions explicitly listed
- [ ] (T2) Key systems documented (if applicable)
