# requirements.md Validation Criteria

## Contents
- [Introduction Provides Clear Context](#1-introduction-provides-clear-context)
- [Alignment with Product Vision Documented](#2-alignment-with-product-vision-documented)
- [User Stories Follow Proper Format](#3-user-stories-follow-proper-format)
- [Acceptance Criteria are Testable](#4-acceptance-criteria-are-testable)
- [Non-Functional Requirements Comprehensive](#5-non-functional-requirements-comprehensive)
- [Dependency Removals/Behavior Parity Explicit](#6-dependency-removalsbehavior-parity-explicit)
- [No Technical Implementation Detail](#7-no-technical-implementation-detail)

### 1. Introduction Provides Clear Context

**Pass:**
- One paragraph explaining what the feature/change is about
- Problem being solved clearly stated
- Scope bounded
- Reader understands "why"

**Fail:**
- Jumps into requirements without context
- Too technical for stakeholders
- Unclear or unbounded scope
- Missing problem explanation

### 2. Alignment with Product Vision Documented

**Pass:**
- References specific product.md sections
- Explains how feature supports product goals
- Connects to documented principles
- Demonstrates awareness of priorities

**Fail:**
- No mention of product.md
- Generic alignment statements
- Feature contradicts product direction
- Missing business value connection

### 3. User Stories Follow Proper Format

**Pass:**
- Uses "As a [role], I want [feature], so that [benefit]"
- Roles are specific (not just "user")
- Features are actionable capabilities
- Benefits explain value proposition
- Stories are independent and testable

**Fail:**
- Mixed/inconsistent formats
- Roles too generic
- Features describe implementation
- Benefits missing or vague
- Compound stories (multiple features)

### 4. Acceptance Criteria are Testable

**Pass:**
- Uses WHEN/THEN or IF/THEN consistently
- Each criterion independently verifiable
- Conditions specific and measurable
- Edge cases addressed
- Happy path and error scenarios covered

**Verification:** Can QA write a test case from each criterion?

**Fail:**
- Vague language ("should work properly")
- Multiple conditions conflated
- Missing error/edge cases
- Cannot derive test cases
- Ambiguous success conditions

### 5. Non-Functional Requirements Comprehensive

**Pass:**
- Performance with specific user-facing metrics (latency, throughput)
- Security stated from user/data-protection perspective
- Reliability expectations (uptime, error recovery, data integrity)
- Usability for user-facing features (accessibility, learning curve)
- Scalability expectations (user count, data volume, concurrent usage)

**Fail:**
- NFR section missing
- Only one NFR type
- Vague metrics ("should be fast")
- Security not considered for sensitive features
- **Engineering design principles stated as user-facing NFRs (SRP, modular
  design, dependency injection) — these belong in design.md**

### 6. Dependency Removals/Behavior Parity Explicit

**Pass:**
- Removed/replaced dependency named explicitly
- Behavior parity stated (same, reduced, changed)
- Trade-offs documented (loss of dynamic updates, etc.)
- New source of truth described
- Migration impact clear

**Fail:**
- Dependency removed without replacement stated
- Assumes parity without explanation
- No mention of runtime/remote changes
- Migration impact unclear

### 7. No Technical Implementation Detail

Per `$SKILLS/sdd-common/references/cross-validation.md § Authority Rules`:
requirements.md owns "what to build and why." Content describing "how to
build it" belongs in design.md. The machine-checkable subset of this rule
is the single source of truth at
`$SKILLS/sdd-common/scripts/sdd_core/data/requirements_antipatterns.yaml`
(human-readable mirror at `$SKILLS/sdd-common/references/requirements-antipatterns.md`).
Enforcement runs inside the review-approval pipeline
(`pre-approval-validation.md § Check 1c`) before this sub-agent launches.

This section calibrates the review agent for the long-tail,
context-dependent cases the validator intentionally does not flag.

**Pass:**
- Requirements describe observable user behavior
- Acceptance criteria use business/domain language
- NFRs state measurable user-facing targets (response time, uptime, concurrent users)
- Technology is referenced only when it IS the user requirement
  (e.g., "support SSO via SAML")

**Fail (review agent catches; validator delegates these by design):**
- Framework-specific implementation flavor ("use a React component for…",
  "Django REST framework view", "Spring Boot controller") — static
  framework lists drift quarterly and are sometimes legitimate product
  context, so the validator delegates here
- Infrastructure choice stated as a user requirement
  ("must run on serverless Lambda") when the user cares about behavior,
  not infrastructure
- Design-pattern-as-requirement ("implement observer pattern for
  notifications") without a user-visible benefit
- Architecture jargon masquerading as acceptance criteria
  ("event-driven pub/sub ingestion")

**Examples:**

| BAD (technical) | GOOD (behavioral) |
|-----------------|-------------------|
| "The system shall use Redis for session caching" | "WHEN a user returns within 30 minutes THEN the system SHALL restore their session without re-authentication" |
| "The UserService class shall validate input" | "WHEN a user submits the form with invalid data THEN the system SHALL display field-specific error messages within 200ms" |
| "POST /api/documents shall accept multipart uploads" | "As a content author, I want to upload documents up to 50MB, so that I can share large files with my team" |
| "The system shall use PostgreSQL with read replicas" | "The system SHALL support 10,000 concurrent read operations with p99 latency under 100ms" |
| "Configure NGINX rate limiting to 100 req/s" | "The system SHALL handle at least 100 requests per second per user without degradation" |
| "Use JWT tokens with RS256 signing" | "WHEN a user authenticates THEN the system SHALL issue a session that expires after 24 hours of inactivity" |
