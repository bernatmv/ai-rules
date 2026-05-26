# General Software Principles Reference

Shared principle set for SDD review skills. Provides two evaluation lenses:
- **Design-level** — for steering doc review (early architectural catch)
- **Code-level** — for implementation review (code quality)

## Contents
- [Override Mechanism](#override-mechanism)
- [Envelope Single-Source Principle](#envelope-single-source-principle)
- [Principles](#principles)
- [Scoring](#scoring)
- [Naming Conventions](#naming-conventions)
- [Canonical Terms](#canonical-terms)
- [Documentation Conventions](#documentation-conventions)

## Override Mechanism

If the user provides custom principles (via prompt, `.sdd-principles.md` in repo root,
or `design.md` § "Design Principles"), use those instead. If the user provides
_additional_ principles ("also check X"), merge with defaults.

**Check order:**
1. User-supplied principles in the current prompt → use those
2. Project-level `.sdd-principles.md` in repo root → use those
3. Spec-level principles in `design.md` § "Design Principles" → use those
4. Fallback → use defaults below

---

## Envelope Single-Source Principle

Every phase envelope satisfies four artifact-role invariants in
mutual consistency: the **next-action surface** (`R-NA`) renders
through `sdd_core.command_templates.build_*_command`, the **lifecycle
mirror** (`R-LM`) constructs through
`sdd_core.required_tool_calls.RequiredToolCallsPayload`, the
**recovery envelope** (`R-RE`) emits through
`sdd_core.output.recoverable_miss`, and the **status tuple** (`R-ST`)
derives from `review_quality.constants.STATUS_FROM_COUNTS`. Tests
freeze the envelope shape so a phase cannot opt out of any of the
four roles.

When in doubt, the rule is one constructor per role. A new phase
satisfies all four invariants by routing through the canonical
constructors; a new emit site that bypasses one is the lint signal
the role-keyed lints catch.

---

## Principles

### DRY (Don't Repeat Yourself)

> Every piece of knowledge should have a single, unambiguous, authoritative
> representation within a system.

**Design-level checks** (steering docs):
- No concept described authoritatively in multiple steering docs
- product.md doesn't restate tech.md's stack; tech.md doesn't restate structure.md's layout
- Patterns defined once in tech.md, applied by reference in structure.md

**Code-level checks** (implementation):
- No copy-pasted code blocks with minor variations
- Shared logic extracted into reusable functions/modules
- Configuration values defined in one place
- Similar patterns use a common abstraction

**Pass/Fail:**
- ✅ Pass: Each knowledge unit has exactly one authoritative source
- ❌ Fail: Same concept defined in 2+ places

### SRP — Single Responsibility Principle

**Design-level checks:**
- Each steering doc has a clear, bounded scope (product = what/why, tech = how, structure = where)
- tech.md doesn't try to define directory layout (that's structure.md's job)
- product.md doesn't specify implementation patterns (that's tech.md's job)
- No steering doc section that belongs in a different doc

**Code-level checks:**
- Each class/module/function has one reason to change
- File length reasonable (< 300 lines for classes, < 50 for functions)
- Function names accurately describe their sole purpose

**Pass/Fail:**
- ✅ Pass: Clear, bounded responsibilities
- ❌ Fail: Mixed responsibilities; "god" objects/documents

### OCP — Open/Closed Principle

**Design-level checks:**
- tech.md describes extensible patterns (plugin/strategy/config-driven)
- Architecture supports adding features without modifying core code
- structure.md organization allows new modules without restructuring existing ones

**Code-level checks:**
- New behavior via extension (new classes/implementations), not modification
- Strategy/plugin patterns where variation is expected
- No growing switch/case statements

**Pass/Fail:**
- ✅ Pass: Extension-friendly design/code
- ❌ Fail: Requires editing stable code/structure for every new feature

### LSP — Liskov Substitution Principle

**Design-level checks:**
- Interfaces/protocols described in tech.md maintain consistent contracts
- Substitutable component designs (any implementation satisfies the interface)

**Code-level checks:**
- Subtypes can replace parent types without breaking behavior
- Overridden methods maintain parent's contract
- No type-checking (instanceof/typeof) to handle subtypes differently

**Applicability:** ➖ N/A when no inheritance/interfaces are present.

### ISP — Interface Segregation Principle

**Design-level checks:**
- tech.md describes focused interfaces, not fat APIs
- Component boundaries in structure.md don't force unnecessary coupling

**Code-level checks:**
- Interfaces are focused and cohesive
- Clients depend only on methods they use
- No "fat" interfaces requiring implementors to stub unused methods

**Applicability:** ➖ N/A when no interfaces are present.

### DIP — Dependency Inversion Principle

**Design-level checks:**
- tech.md architecture depends on abstractions, not concretions
- Module boundaries in structure.md allow dependency injection
- No hardcoded infrastructure dependencies in the architecture description

**Code-level checks:**
- High-level modules depend on abstractions (interfaces/protocols)
- Dependencies injected, not instantiated internally
- Concrete implementations are swappable

**Pass/Fail:**
- ✅ Pass: Abstractions at boundaries
- ❌ Fail: Direct coupling to concrete implementations in design or code

### KISS — Keep It Simple, Stupid

**Design-level checks:**
- Architecture is no more complex than the problem requires
- No premature abstraction in the design (abstractions justified by actual variation)
- Steering docs are clear and concise, not over-specified

**Code-level checks:**
- Simplest approach that meets requirements
- Standard library used where sufficient
- No over-engineering

### YAGNI — You Aren't Gonna Need It

**Design-level checks:**
- Architecture doesn't include speculative components without backing requirements
- No "future-proofing" infrastructure without documented need
- Steering docs don't describe features that aren't planned

**Code-level checks:**
- Only implements what the current task requires
- No unused parameters/flags "for future use"
- No code paths unreachable under current requirements

---

## Scoring

| Principle | Weight | Rating |
|-----------|--------|--------|
| DRY | High | ✅ Pass / ⚠️ Partial / ❌ Fail |
| SRP | High | ✅ / ⚠️ / ❌ |
| OCP | Medium | ✅ / ⚠️ / ❌ |
| LSP | Low (when applicable) | ✅ / ⚠️ / ❌ / ➖ N/A |
| ISP | Low (when applicable) | ✅ / ⚠️ / ❌ / ➖ N/A |
| DIP | Medium | ✅ / ⚠️ / ❌ |
| KISS | High | ✅ / ⚠️ / ❌ |
| YAGNI | Medium | ✅ / ⚠️ / ❌ |

**Overall Principles Score:** X/5 — weighted average of applicable principles.

---

## Naming Conventions

All SDD project and spec names use kebab-case: `^[a-z0-9]+(-[a-z0-9]+)*$`

Examples: `user-onboarding`, `payment-flow-v2`, `fix-login-sso-failure`

The canonical regex constant is `sdd_core.text.KEBAB_RE`.

### PRD Filename Convention

PRD filenames must contain `prd` (case-insensitive) for auto-detection.
The canonical detection function is `discovery.shared.is_prd_filename()`.

| Valid | Invalid (won't auto-detect as PRD) |
|-------|-------------------------------------|
| `prd.md` | `requirements.md` |
| `prd-v1.md` | `product-doc.md` |
| `prd-onboarding.md` | `notes.md` |
| `prd-payments-flow.md` | |

### Approval Categories

| Category | `categoryName` value | Used by |
|----------|---------------------|---------|
| `spec` | Spec name (kebab-case) | `sdd-create-spec`, `sdd-manage-status` |
| `steering` | `"steering"` (literal) | `sdd-create-steering` |
| `discovery` | Discovery project name (kebab-case) | `sdd-create-prd` |

> **Note:** For discovery projects with multiple PRDs, approval and quality artifacts
> scope to the project level (`categoryName` = project name), not individual PRDs.
> Per-PRD status is tracked via manifest `set-artifact-status`.

The canonical constant is `sdd_core.approvals.APPROVAL_CATEGORIES`.

## Canonical Terms

| Concept | Canonical Term | Do NOT use |
|---------|---------------|------------|
| Discovery project | "discovery project" | "discovery folder", "discovery directory" |
| Approval rejection | "needs_revision" (scripts), "request revision" (user-facing) | "reject revision", "revision needed" |
| Feature identifier | "feature-name" (kebab-case) | "project-name" (reserved for workspace), "spec-name" (reserved for spec) |
| PRD location | `.spec-workflow/discovery/{feature-name}/{prd-name}` | — |
| PRD filename | Any file matching `prd` (case-insensitive). Default: `prd.md` | — |

## Documentation Conventions

- Files >100 lines must have a `## Contents` TOC
- TOC entries must use markdown links: `- [Title](#anchor)`
- Anchor slugs follow GitHub conventions (lowercase, hyphens, no special chars)
