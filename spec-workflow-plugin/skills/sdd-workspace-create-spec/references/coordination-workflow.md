# Coordination Workflow Reference

## Contents

- [Repo-Scoping Principle](#repo-scoping-principle)
- [Cross-Repo Scope Section](#cross-repo-scope-section)
- [Per-Repo Design Delegation](#per-repo-design-delegation)
- [Task Metadata Fields](#task-metadata-fields)
- [Coordination tasks.md Example](#coordination-tasksmd-example)
- [Delegation Context Usage (Per-Phase)](#delegation-context-usage-per-phase)

## Repo-Scoping Principle

The coordinator's documents are created **phase-by-phase** alongside all other
repos (not all at once upfront). Each phase creates one document type for the
coordinator, then for all target repos, before moving to the next phase.

Each repo's spec documents (requirements.md, design.md, tasks.md) describe
only that repo's own deliverables. The coordination spec describes the
coordinator repo's work — which may be purely orchestration with no code changes.

| Content | Belongs in | Does NOT belong in |
|---------|-----------|-------------------|
| Sub-repo UI components | Sub-spec | Coordination spec |
| Sub-repo API routes | Sub-spec | Coordination spec |
| Sub-repo internal interfaces | Sub-spec | Coordination spec |
| Cross-repo data format contracts | Coordination spec (integration points) | — |
| Delegation tasks with `_Repo_` | Coordination spec tasks.md | — |

If the coordinator has no implementation work, set `skipPhases` for the
coordinator in the manifest (see `manifest-schema.md`), or keep its
requirements.md and design.md short (~25–50 lines), documenting only
cross-repo scope and integration contracts.

## Cross-Repo Scope Section

The coordination `requirements.md` includes a `## Cross-Repo Scope` section that declares participating repositories, their roles, and boundaries.

**Render via the `workspace-requirements` template variant** — the
section stub is already present in the canonical
`.spec-workflow/templates/workspace-requirements-template.md`. Swap
`--type requirements` with `--type workspace-requirements`:

```
.spec-workflow/sdd util/resolve-template.py \
  --type workspace-requirements --spec-name {subSpecName} \
  --content --workspace {repoPath}
```

**Guidelines:**
- Each repo has a unique `id` matching the manifest `repos[].id`
- `Role` describes what the repo contributes to the feature
- `Boundary` clarifies what the repo does NOT handle

## Per-Repo Design Delegation

The coordination `design.md` maps design sections to target repos using headings that match repo IDs.

**Format:** Use summary-level delegation descriptions. Detailed component design
belongs in sub-specs, not the coordination spec.

```markdown
## Backend Delegation (backend)

Backend will implement auth API endpoints and JWT middleware.
Key integration point: POST /auth/login returns { accessToken, refreshToken }.
See sub-spec user-auth-backend for full design.

## Frontend Delegation (frontend)

Frontend will implement auth UI and token management.
Consumes the auth API defined by the backend sub-spec.
See sub-spec user-auth-frontend for full design.

## API Contracts

### POST /auth/login
- Request: { email: string, password: string }
- Response: { accessToken: string, refreshToken: string }
```

| Repo ID | Role | Design Section Reference | API Contracts |
|---------|------|------------------------|---------------|
| backend | API + auth | "Backend Delegation (backend)" | Server-side endpoints |
| frontend | UI + token mgmt | "Frontend Delegation (frontend)" | Client-side consumption |

## Task Metadata Fields

Workspace coordination tasks use the existing `_Key: Value_` italic metadata syntax.

| Field | Syntax | Validation | Purpose |
|-------|--------|-----------|---------|
| `_Repo: {repo-id}_` | Non-empty string | Must match a repo ID in manifest | Target repo for sub-spec |
| `_SubSpec: {spec-name}_` | Kebab-case, non-empty | Must be valid kebab-case | Sub-spec name in target repo |
| `_DependsOn: {task-ids}_` | Comma-separated IDs | All IDs must exist in task list | Cross-task dependency ordering |

The existing `METADATA_RE` regex in `sdd_core/tasks.py` captures `_Key: Value_` generically.
These fields work with the existing regex without modification.

## Coordination tasks.md Example

```markdown
---
spec-version: 0.4.0
---
# Tasks: user-authentication

## Sub-Spec Creation

- [ ] 1 Create and implement backend auth sub-spec
  - _Requirements: 1.1, 1.2_
  - _Repo: backend_
  - _SubSpec: user-auth-backend_
  - _Prompt: Implement the task for spec user-authentication.
    Role: API developer | Task: Create backend auth sub-spec |
    Restrictions: Server-side only | Success: Sub-spec validated |
    Before starting: (1) mark [-]. (2) Search logs.
    After: (3) .spec-workflow/sdd util/log-implementation.py. (4) mark [x]._

- [ ] 2 Create and implement frontend auth sub-spec
  - _Requirements: 1.3_
  - _Repo: frontend_
  - _SubSpec: user-auth-frontend_
  - _DependsOn: 1_
  - _Prompt: Implement the task for spec user-authentication.
    Role: Frontend developer | Task: Create frontend auth sub-spec |
    Restrictions: Client-side only | Success: Sub-spec validated |
    Before starting: (1) mark [-]. (2) Search logs.
    After: (3) .spec-workflow/sdd util/log-implementation.py. (4) mark [x]._

## Integration Tasks

- [ ] 3 Cross-repo integration verification
  - _Requirements: 2.1_
  - _Prompt: Implement the task for spec user-authentication.
    Role: Integration tester | Task: Verify cross-repo contracts |
    Restrictions: Read-only verification | Success: All contracts satisfied |
    Before starting: (1) mark [-]. (2) Search logs.
    After: (3) .spec-workflow/sdd util/log-implementation.py. (4) mark [x]._
```

## Delegation Context Usage (Per-Phase)

During each phase, the delegation context seeds content for the current document
only. See `phase-loop.md` § Phase R — Requirements and § Phase D — Design & Phase T — Tasks for phase-specific usage.

| Delegation Context Field | Target Document | How to Use |
|-------------------------|-----------------|-----------|
| `role` | requirements.md, design.md | Defines the scope and architectural boundary |
| `requirements_subset` | requirements.md | Seeds the requirements specific to this repo |
| `design_section` | design.md | Seeds the design content for this repo's component |
| `api_contracts` | design.md | Included in the API Design section |
| `depends_on_context` | tasks.md | Creates dependency notes in task metadata |
