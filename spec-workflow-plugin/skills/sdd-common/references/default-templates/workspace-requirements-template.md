# Requirements Document

<!-- Authoring rules: see $SKILLS/sdd-common/references/requirements-antipatterns.md for the canonical "what doesn't belong here" list (enforced by spec/lint-requirements.py). -->

## Introduction

[Provide a brief overview of the feature, its purpose, and its value to users.
For workspace specs, focus on cross-repo coordination and shared user-facing
outcomes.]

## Alignment with Product Vision

[Explain how this feature supports the goals outlined in product.md.]

## Requirements

### Requirement 1

**User Story:** As a [role], I want [feature], so that [benefit]

#### Acceptance Criteria

1. WHEN [event] THEN [system] SHALL [response]
2. IF [precondition] THEN [system] SHALL [response]
3. WHEN [event] AND [condition] THEN [system] SHALL [response]

### Requirement 2

**User Story:** As a [role], I want [feature], so that [benefit]

#### Acceptance Criteria

1. WHEN [event] THEN [system] SHALL [response]
2. IF [precondition] THEN [system] SHALL [response]

## Non-Functional Requirements

### Performance
- [Response time, throughput, or latency targets users will experience]

### Security
- [Data protection, access control, or privacy requirements from user perspective]

### Reliability
- [Uptime, error recovery, or data integrity expectations]

### Usability
- [Accessibility, ease-of-use, or learning curve requirements]

### Scalability
- [Growth expectations — user count, data volume, concurrent usage]

## Cross-Repo Scope

| Repo ID | Role | Boundary |
|---------|------|----------|
| <coordinator-repo-id> | Coordinator (this repo) | Owns workspace tracker; does not perform domain work |
| <repo-id> | <role e.g. Coordinator / Target> | <what it does NOT do> |

## Open Questions

<!-- Optional: items deferred to design phase. Delete this section if empty. -->
- [ ] <Open question 1>
