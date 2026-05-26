# Cross-Document Validation Framework

Reusable pattern for detecting issues across related documents. Used by
`sdd-review-steering-docs` (product↔tech↔structure) and
`sdd-review-spec-docs` (requirements↔design↔tasks).


## Contents

- [Issue Categories](#issue-categories)
- [Detection Approach](#detection-approach)
- [Authority Rules](#authority-rules)
- [Report Template](#report-template)

## Issue Categories

| Category | Definition | Severity |
|----------|-----------|----------|
| **Duplication** | Same concept described in multiple documents with different wording | 🟡 Warning |
| **Conflict** | Two documents make contradictory claims about the same topic | 🔴 Critical |
| **Gap** | A concept referenced in one document has no corresponding coverage in the expected related document | 🟡 Warning |
| **Drift** | Documents were once consistent but one has been updated while the other has not | 🟡 Warning |

## Detection Approach

For each pair of documents in the review set:

1. **Identify shared topics**: Extract key concepts, technology names, feature names,
   architectural patterns, and component names from both documents
2. **Compare coverage**: For each shared topic, compare how each document describes it
3. **Classify issues**: Tag each finding as Duplication / Conflict / Gap / Drift
4. **Generate recommendations**: For each issue, recommend which document should be
   the single source of truth (authority) and what the other document should do
   (reference, remove, or update)

## Authority Rules

Each topic should have exactly one authoritative document. When duplication or
conflict is found, recommend consolidation to the authority:

| Topic Type | Authority Document | Other Docs Should |
|-----------|-------------------|------------------|
| Product vision, goals, features | product.md | Reference, not repeat |
| Technology choices, versions, patterns | tech.md | Reference, not repeat |
| Directory structure, file conventions | structure.md | Reference, not repeat |
| Requirements, acceptance criteria | requirements.md | Reference, not repeat |
| Architecture decisions, component design | design.md | Reference, not repeat |
| Task breakdown, implementation order | tasks.md | Reference, not repeat |

## Report Template

| # | Documents | Topic | Issue Type | Severity | Recommendation |
|---|-----------|-------|-----------|----------|---------------|
| 1 | [doc A] ↔ [doc B] | [topic] | [Duplication/Conflict/Gap/Drift] | [🔴/🟡] | [action] |
