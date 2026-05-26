# requirements.md Antipatterns

> **Source of truth:** `../scripts/sdd_core/data/requirements_antipatterns.yaml`
>
> This document is a human-readable mirror. Behavior is defined by the
> YAML file; if they disagree, the YAML wins. The CI guard
> `tests/_support/antipattern_data_validator.py` keeps the YAML
> well-formed (invoked from `tests/test_requirements_antipatterns_data.py`).

## Contents

- [Overview](#overview)
- [Authority Rule](#authority-rule)
- [Rule Groups](#rule-groups)
  - [path — severity: error](#path--severity-error)
  - [code — severity: warning](#code--severity-warning)
  - [tech-stack — severity: warning (info inside NFR)](#tech-stack--severity-warning-info-inside-nfr)
  - [api-config — severity: warning](#api-config--severity-warning)
  - [architecture-concepts — severity: info (escalates to warning under NFR)](#architecture-concepts--severity-info-escalates-to-warning-under-nfr)
  - [architecture-impl — severity: info](#architecture-impl--severity-info)
  - [structural — severity: error](#structural--severity-error)
- [Severity Summary](#severity-summary)
- [Bug-Fix Mode](#bug-fix-mode)
- [Suppression Mechanism](#suppression-mechanism)
- [What the Validator Does NOT Catch](#what-the-validator-does-not-catch)
- [Problem-Statement Solution Markers](#problem-statement-solution-markers)

## Overview

`requirements.md` describes **what to build and why**. Implementation details
("how to build it") belong in `design.md`. The antipattern rules below detect
leakage deterministically — the review sub-agent handles semantic judgment
calibrated by `$SKILLS/sdd-review-spec-docs/references/validation-criteria-requirements.md § 7`.

The rules run automatically inside the review-approval pipeline via
`pre-approval-validation.md § Check 1c` (see
`sdd-common/scripts/spec/lint-requirements.py`).

## Authority Rule

Per `$SKILLS/sdd-common/references/cross-validation.md § Authority Rules`:

| Document | Authority | Other docs |
|----------|-----------|-----------|
| `requirements.md` | Requirements, acceptance criteria, user-facing NFRs | Reference, not repeat |
| `design.md` | Architecture, components, file paths, tech stack | Reference, not repeat |
| `tasks.md` | Implementation order, file operations | Reference, not repeat |

## Rule Groups

Six semantic groups. The same names are used in YAML, JSON output,
suppression tags, and §7 prose.

### `path` — severity: `error`

Paths and source file references are always wrong in requirements.md.

| Rule | Matches | Suggestion |
|------|---------|------------|
| `path-literal` | `src/components/`, `./lib/utils`, `path/to/file.ext` | Drop the path; describe user-facing behavior |
| `import-statement` | `import X from '…'`, `from X import Y`, `require('…')` | Imports belong in design.md or tasks.md |
| `source-extension` | Words ending in `.py`, `.ts`, `.tsx`, `.js`, `.jsx`, `.vue`, `.go`, `.rs`, `.java`, `.rb`, `.kt`, `.swift` | Describe what the user does, not where code lives |

### `code` — severity: `warning`

High-precision token-anchored patterns only — no bare camelCase/snake_case
(false-positive risk on iPhone, eCommerce, SaaS, GitHub, JavaScript, macOS).

| Rule | Pattern anchor |
|------|---------------|
| `function-call` | `name(` on same logical line |
| `method-access` | `identifier.method(` |
| `class-declaration` | `class Name:` / `class Name {` / `interface IName` |
| `function-declaration` | `def name(` / `function name(` / `const name = (…) =>` / `=> {` |
| `type-annotation` | `: string[]`, `: number`, `Optional[…]`, `Dict[…, …]`, `Promise<…>`, `Observable<…>` |

In bug-fix mode, `class-declaration` and `function-declaration` drop to `info`.

### `tech-stack` — severity: `warning` (info inside NFR)

A short sentinel list. Long-tail framework detection (`React`, `Django`,
`Next.js`) is delegated to the review sub-agent — static lists drift over
time and the reviewer can apply context.

| Category | Sentinels |
|----------|-----------|
| Data stores | Redis, PostgreSQL, MySQL, MongoDB, DynamoDB, Elasticsearch, Cassandra |
| Infra/runtime | Docker, Kubernetes, Lambda, Nginx, Terraform |
| Package managers | npm, pip, cargo, maven (only when co-occurring with install/package/dependency) |

Inside `## Non-Functional Requirements`, severity drops to `info` — PMs
sometimes legitimately specify platform constraints there.

### `api-config` — severity: `warning`

| Rule | Pattern | Suggestion |
|------|---------|------------|
| `http-route` | `GET /…`, `POST /…`, etc. | Replace route with a WHEN/THEN behavior |
| `status-code-literal` | `200 OK`, `401 Unauthorized`, `404 Not Found`, etc. | Describe the observable outcome |
| `env-var-shape` | `$VAR`, `${VAR}` | Configuration belongs in design.md |
| `env-var-literals` | `DATABASE_URL`, `API_KEY`, `NODE_ENV`, … | Configuration belongs in design.md |
| `connection-string` | `postgres://`, `mongodb://`, `redis://`, `amqp://` prefixes | Connection details belong in design.md |

### `architecture-concepts` — severity: `info` (escalates to `warning` under NFR)

Engineering principles that belong in `design.md`. NFR-section mentions are the
common leakage vector — the reviewer gate escalates to `warning` automatically
via `section_aware` (mirrors the existing `tech-stack` NFR rule).

| Terms |
|-------|
| SRP, SOLID, single responsibility, open/closed principle, liskov substitution |
| dependency injection, interface segregation, inversion of control |
| factory pattern, observer pattern, strategy pattern, decorator pattern, repository pattern |
| singleton |

### `architecture-impl` — severity: `info`

Implementation-layer vocabulary that frequently appears in legitimate NFR
constraints ("must run behind middleware", "scale via sharding"). Left at `info`
everywhere — the reviewer sub-agent catches egregious cases. Does **not**
escalate under NFR to preserve NFR writability.

| Terms |
|-------|
| middleware, microservice, monolith, event bus, pub/sub, message queue, CQRS, event sourcing, saga |
| ORM, schema migration, foreign key, sharding, replication |

### `structural` — severity: `error`

Deterministic structural validation consistent with `doc_validation.py`.

| Check | Condition | Granularity |
|-------|-----------|-------------|
| `headings-required` | Introduction, Requirements, Non-Functional Requirements present | Section |
| `user-story-present` | At least one `As a [role], I want …, so that …` paragraph | Paragraph (via `iter_paragraphs`) |
| `acceptance-criterion-present` | At least one `WHEN`/`IF` … `THEN` … `SHALL` paragraph | Paragraph (via `iter_paragraphs`) |
| `no-empty-requirement-sections` | Each `### Requirement N` subsection has body content | Section |

Paragraph-level rules collapse soft line-wraps — a wrapped user story or
acceptance criterion still matches. A **blank line** is a paragraph
boundary: avoid inserting one in the middle of a user-story or AC line,
or the validator will flag the paragraph as split. When the marker
(`**User Story:**` / `WHEN`/`THEN`/`SHALL`) is present but the full
regex fails on any paragraph, the error message calls out the marker
so the author can fix the missing clause rather than guessing.

## Severity Summary

| Severity | Meaning | Exit behavior |
|----------|---------|---------------|
| `error` | Structural failure OR deterministically-wrong content (`path`, `structural`) | Exit 1 — pipeline blocks |
| `warning` | High-precision leakage signal (`code`, `tech-stack` outside NFR, `api-config`) | Exit 0 — agent rephrases |
| `info` | Borderline term (`tech-stack` inside NFR, `architecture-impl`, `architecture-concepts` outside NFR) | Exit 0 — agent reviews |

## Bug-Fix Mode

Bug-fix specs legitimately cite file paths, affected classes, and
component boundaries. Detection shares the canonical word list in
`sdd_core.specs.BUG_FIX_WORDS`. Either signal triggers bug-fix mode:

1. Spec name matches `BUG_FIX_WORDS` (e.g. `fix-*`, `*-bugfix-*`)
2. Explicit `--mode bug-fix` CLI flag

In bug-fix mode:

- `path` severity: `error` → `info`
- `code` rules `class-declaration` / `function-declaration`: `warning` → `info`
- `tech-stack`, `api-config`, `architecture`, `structural`: unchanged

## Suppression Mechanism

Single minimal mechanism. Errors cannot be suppressed (if you need a file
path in requirements, the doc is in the wrong place).

```markdown
<!-- rq-ignore: tech-stack -->
- The system SHALL integrate with the existing Okta SAML identity provider
```

The HTML comment on the line **immediately preceding** a flagged line
suppresses `warning` / `info` findings from the named group (`path`,
`code`, `tech-stack`, `api-config`, `architecture`).

## What the Validator Does NOT Catch

The validator is intentionally high-precision. The following cases are
delegated to the review sub-agent via
`$SKILLS/sdd-review-spec-docs/references/validation-criteria-requirements.md § 7`:

- Framework-flavored implementation ("use a React component for…")
- Infrastructure-as-requirement ("must run on serverless Lambda")
- Pattern-as-requirement ("implement observer pattern for notifications")
- Architecture jargon masquerading as acceptance criteria

See the §7 BAD/GOOD example table for calibration examples.

## Problem-Statement Solution Markers

Run `.spec-workflow/sdd prd/validate-readiness.py --target
{feature-name} --gate pre-requirements --session-file
.spec-workflow/discovery/{feature-name}/.session-state.json` to scan
the `problem_statement.text` field for solution-vocabulary literals.
Matches surface as a `warn`-tier advisory so the authoring agent
self-corrects before the PRD materialises on disk — they never fail
the gate. Markers live under `problem_statement.solution_markers` in
`../scripts/sdd_core/data/requirements_antipatterns.yaml`. Advisory
`name`: `problem_statement_solution_marker` — grep that literal to
locate the responsible validator.
