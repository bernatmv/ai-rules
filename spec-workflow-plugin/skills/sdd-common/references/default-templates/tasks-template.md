# Tasks Document

## Contents

- [Implementation ritual](#implementation-ritual)
- [Example Task Checklist](#example-task-checklist)

## Implementation ritual

Apply this four-step ritual to **every** task below before moving to the next checklist item:

1. Mark the task as in-progress: change `[ ]` to `[-]` in `tasks.md`.
2. Search existing Implementation Logs for reusable code under `.spec-workflow/impl-log/{spec_name}/`.
3. After implementation **and** testing, call `.spec-workflow/sdd util/log-implementation.py` to record what was done. This MUST succeed before proceeding.
4. Only after log-implementation succeeds, mark the task complete: change `[-]` to `[x]` in `tasks.md`.

Each `_Prompt:` block below ends with the same four-step suffix so the validator and the renderer share one literal — see `sdd_core.task_prompts` for the canonical strings.

## Example Task Checklist

- [ ] 1. Create core interfaces in src/types/feature.ts
  - File: src/types/feature.ts
  - Define TypeScript interfaces for the feature data structures, extending base types in `src/types/base.ts`.
  - _Leverage: src/types/base.ts_
  - _Requirements: 1.1_
  - _Prompt: Implement the task for spec {spec_name}: Role: TypeScript developer | Task: define interfaces for the feature data structures (req 1.1) extending the base types in src/types/base.ts | Restrictions: do not modify the base interfaces; preserve backward compatibility | Success: interfaces compile, base inheritance is correct, full type coverage for the requirement.

Before starting implementation: (1) mark this task as in_progress by changing [ ] to [-] in tasks.md. (2) Search existing Implementation Logs for reusable code under `.spec-workflow/impl-log/{spec_name}/`. After implementation and testing: (3) call `.spec-workflow/sdd util/log-implementation.py` to record what was done — this MUST succeed before proceeding. (4) Only after log-implementation succeeds, mark the task complete by changing [-] to [x] in tasks.md._

- [ ] 2. Create base model class in src/models/FeatureModel.ts
  - File: src/models/FeatureModel.ts
  - Implement a base model extending `BaseModel` and add validation via `src/utils/validation.ts`.
  - _Leverage: src/models/BaseModel.ts, src/utils/validation.ts_
  - _Requirements: 2.1_
  - _Prompt: Implement the task for spec {spec_name}: Role: backend developer | Task: implement a base model that extends BaseModel and uses validation utilities (req 2.1) | Restrictions: follow existing model patterns; never bypass the validation utilities | Success: model extends BaseModel, validation methods covered by tests, error handling consistent with sibling models.

Before starting implementation: (1) mark this task as in_progress by changing [ ] to [-] in tasks.md. (2) Search existing Implementation Logs for reusable code under `.spec-workflow/impl-log/{spec_name}/`. After implementation and testing: (3) call `.spec-workflow/sdd util/log-implementation.py` to record what was done — this MUST succeed before proceeding. (4) Only after log-implementation succeeds, mark the task complete by changing [-] to [x] in tasks.md._

- [ ] 3. Add CRUD methods to FeatureModel.ts
  - File: src/models/FeatureModel.ts (continue from task 2)
  - Implement create / update / delete plus relationship handling for foreign keys.
  - _Leverage: src/models/BaseModel.ts_
  - _Requirements: 2.2, 2.3_
  - _Prompt: Implement the task for spec {spec_name}: Role: backend developer with ORM expertise | Task: implement CRUD methods and relationship handling on FeatureModel (req 2.2, 2.3) | Restrictions: maintain transaction integrity; follow existing relationship patterns; do not duplicate BaseModel behaviour | Success: each operation is transactional, relationships covered by tests, behaviour aligned with sibling models.

Before starting implementation: (1) mark this task as in_progress by changing [ ] to [-] in tasks.md. (2) Search existing Implementation Logs for reusable code under `.spec-workflow/impl-log/{spec_name}/`. After implementation and testing: (3) call `.spec-workflow/sdd util/log-implementation.py` to record what was done — this MUST succeed before proceeding. (4) Only after log-implementation succeeds, mark the task complete by changing [-] to [x] in tasks.md._

- [ ] 4. Create model unit tests in tests/models/FeatureModel.test.ts
  - File: tests/models/FeatureModel.test.ts
  - Cover validation and CRUD methods for `FeatureModel`.
  - _Leverage: tests/helpers/testUtils.ts, tests/fixtures/data.ts_
  - _Requirements: 2.1, 2.2_
  - _Prompt: Implement the task for spec {spec_name}: Role: QA engineer | Task: add unit tests for FeatureModel validation and CRUD (req 2.1, 2.2) | Restrictions: cover both success and failure paths; do not test external dependencies directly; keep tests isolated | Success: full coverage for validation + CRUD methods, fixtures sourced from tests/fixtures/data.ts.

Before starting implementation: (1) mark this task as in_progress by changing [ ] to [-] in tasks.md. (2) Search existing Implementation Logs for reusable code under `.spec-workflow/impl-log/{spec_name}/`. After implementation and testing: (3) call `.spec-workflow/sdd util/log-implementation.py` to record what was done — this MUST succeed before proceeding. (4) Only after log-implementation succeeds, mark the task complete by changing [-] to [x] in tasks.md._

- [ ] 5. Create service interface in src/services/IFeatureService.ts
  - File: src/services/IFeatureService.ts
  - Define the service contract; extend `IBaseService`.
  - _Leverage: src/services/IBaseService.ts_
  - _Requirements: 3.1_
  - _Prompt: Implement the task for spec {spec_name}: Role: software architect | Task: design the IFeatureService contract extending IBaseService (req 3.1) | Restrictions: respect interface segregation; do not expose internal implementation details; keep the contract DI-friendly | Success: method signatures explicit, interface ready for the DI container, all required service operations covered.

Before starting implementation: (1) mark this task as in_progress by changing [ ] to [-] in tasks.md. (2) Search existing Implementation Logs for reusable code under `.spec-workflow/impl-log/{spec_name}/`. After implementation and testing: (3) call `.spec-workflow/sdd util/log-implementation.py` to record what was done — this MUST succeed before proceeding. (4) Only after log-implementation succeeds, mark the task complete by changing [-] to [x] in tasks.md._

- [ ] 6. Implement feature service in src/services/FeatureService.ts
  - File: src/services/FeatureService.ts
  - Concrete service using `FeatureModel`; surface errors via `src/utils/errorHandler.ts`.
  - _Leverage: src/services/BaseService.ts, src/utils/errorHandler.ts, src/models/FeatureModel.ts_
  - _Requirements: 3.2_
  - _Prompt: Implement the task for spec {spec_name}: Role: backend developer | Task: implement FeatureService using FeatureModel and BaseService patterns (req 3.2) | Restrictions: implement the interface contract exactly; never bypass model validation; route errors through errorHandler.ts | Success: every interface method implemented, errors handled consistently, business logic isolated from data-layer concerns.

Before starting implementation: (1) mark this task as in_progress by changing [ ] to [-] in tasks.md. (2) Search existing Implementation Logs for reusable code under `.spec-workflow/impl-log/{spec_name}/`. After implementation and testing: (3) call `.spec-workflow/sdd util/log-implementation.py` to record what was done — this MUST succeed before proceeding. (4) Only after log-implementation succeeds, mark the task complete by changing [-] to [x] in tasks.md._

- [ ] 7. Add service DI registration in src/utils/di.ts
  - File: src/utils/di.ts (modify existing)
  - Register `FeatureService`; configure lifetime + dependencies.
  - _Leverage: existing DI configuration in src/utils/di.ts_
  - _Requirements: 3.1_
  - _Prompt: Implement the task for spec {spec_name}: Role: DevOps engineer | Task: register FeatureService in the DI container (req 3.1) | Restrictions: follow existing DI patterns; avoid circular dependencies; document the chosen lifetime inline | Success: service resolves at runtime, dependencies wired correctly, lifetime fits the call sites.

Before starting implementation: (1) mark this task as in_progress by changing [ ] to [-] in tasks.md. (2) Search existing Implementation Logs for reusable code under `.spec-workflow/impl-log/{spec_name}/`. After implementation and testing: (3) call `.spec-workflow/sdd util/log-implementation.py` to record what was done — this MUST succeed before proceeding. (4) Only after log-implementation succeeds, mark the task complete by changing [-] to [x] in tasks.md._

- [ ] 8. Create service unit tests in tests/services/FeatureService.test.ts
  - File: tests/services/FeatureService.test.ts
  - Mock dependencies; cover happy path + error scenarios.
  - _Leverage: tests/helpers/testUtils.ts, tests/mocks/modelMocks.ts_
  - _Requirements: 3.2, 3.3_
  - _Prompt: Implement the task for spec {spec_name}: Role: QA engineer | Task: add FeatureService unit tests with mocked dependencies (req 3.2, 3.3) | Restrictions: mock all external dependencies; exercise business logic in isolation; do not test framework code | Success: business logic and error scenarios both covered, dependencies mocked, tests deterministic.

Before starting implementation: (1) mark this task as in_progress by changing [ ] to [-] in tasks.md. (2) Search existing Implementation Logs for reusable code under `.spec-workflow/impl-log/{spec_name}/`. After implementation and testing: (3) call `.spec-workflow/sdd util/log-implementation.py` to record what was done — this MUST succeed before proceeding. (4) Only after log-implementation succeeds, mark the task complete by changing [-] to [x] in tasks.md._

- [ ] 9. Plan API structure
  - Plan REST routes, request/response shapes, and versioning.
  - _Leverage: src/api/baseApi.ts, src/utils/apiUtils.ts_
  - _Requirements: 4.0_
  - _Prompt: Implement the task for spec {spec_name}: Role: API architect | Task: plan the REST API surface (req 4.0) using baseApi.ts and apiUtils.ts | Restrictions: follow REST conventions; preserve API versioning compatibility; do not expose internal data shapes | Success: route table documented, status codes mapped, versioning strategy explicit.

Before starting implementation: (1) mark this task as in_progress by changing [ ] to [-] in tasks.md. (2) Search existing Implementation Logs for reusable code under `.spec-workflow/impl-log/{spec_name}/`. After implementation and testing: (3) call `.spec-workflow/sdd util/log-implementation.py` to record what was done — this MUST succeed before proceeding. (4) Only after log-implementation succeeds, mark the task complete by changing [-] to [x] in tasks.md._

- [ ] 9.1 Set up routing and middleware
  - Configure routes; wire auth + error-handling middleware.
  - _Leverage: src/middleware/auth.ts, src/middleware/errorHandler.ts_
  - _Requirements: 4.1_
  - _Prompt: Implement the task for spec {spec_name}: Role: backend developer | Task: configure routes plus auth and error middleware (req 4.1) | Restrictions: keep middleware ordering explicit; never bypass security middleware; ensure errors propagate through errorHandler.ts | Success: routes load, auth enforced, errors handled gracefully through the request lifecycle.

Before starting implementation: (1) mark this task as in_progress by changing [ ] to [-] in tasks.md. (2) Search existing Implementation Logs for reusable code under `.spec-workflow/impl-log/{spec_name}/`. After implementation and testing: (3) call `.spec-workflow/sdd util/log-implementation.py` to record what was done — this MUST succeed before proceeding. (4) Only after log-implementation succeeds, mark the task complete by changing [-] to [x] in tasks.md._

- [ ] 9.2 Implement CRUD endpoints
  - Create endpoints; add request validation + integration tests.
  - _Leverage: src/controllers/BaseController.ts, src/utils/validation.ts_
  - _Requirements: 4.2, 4.3_
  - _Prompt: Implement the task for spec {spec_name}: Role: full-stack developer | Task: implement CRUD endpoints extending BaseController (req 4.2, 4.3) | Restrictions: validate every input via validation.ts; follow existing controller patterns; honour the route-plan status codes | Success: endpoints return correct status codes, validation rejects bad input, integration tests cover the matrix.

Before starting implementation: (1) mark this task as in_progress by changing [ ] to [-] in tasks.md. (2) Search existing Implementation Logs for reusable code under `.spec-workflow/impl-log/{spec_name}/`. After implementation and testing: (3) call `.spec-workflow/sdd util/log-implementation.py` to record what was done — this MUST succeed before proceeding. (4) Only after log-implementation succeeds, mark the task complete by changing [-] to [x] in tasks.md._

- [ ] 10. Plan component architecture
  - Plan reusable components; align with the design system.
  - _Leverage: src/components/BaseComponent.tsx, src/styles/theme.ts_
  - _Requirements: 5.0_
  - _Prompt: Implement the task for spec {spec_name}: Role: frontend architect | Task: plan the component tree (req 5.0) leveraging BaseComponent and theme.ts | Restrictions: follow existing component patterns; maintain design-system consistency; document reusability boundaries | Success: hierarchy documented, theme reused, component boundaries explicit.

Before starting implementation: (1) mark this task as in_progress by changing [ ] to [-] in tasks.md. (2) Search existing Implementation Logs for reusable code under `.spec-workflow/impl-log/{spec_name}/`. After implementation and testing: (3) call `.spec-workflow/sdd util/log-implementation.py` to record what was done — this MUST succeed before proceeding. (4) Only after log-implementation succeeds, mark the task complete by changing [-] to [x] in tasks.md._

- [ ] 10.1 Create base UI components
  - Implement reusable components and theme integration.
  - _Leverage: src/components/BaseComponent.tsx, src/styles/theme.ts_
  - _Requirements: 5.1_
  - _Prompt: Implement the task for spec {spec_name}: Role: frontend developer | Task: build reusable UI components extending BaseComponent (req 5.1) using the existing theme system | Restrictions: source theme tokens from theme.ts; follow component composition patterns; preserve accessibility | Success: components reusable and themed, accessibility checks pass, responsive on the documented breakpoints.

Before starting implementation: (1) mark this task as in_progress by changing [ ] to [-] in tasks.md. (2) Search existing Implementation Logs for reusable code under `.spec-workflow/impl-log/{spec_name}/`. After implementation and testing: (3) call `.spec-workflow/sdd util/log-implementation.py` to record what was done — this MUST succeed before proceeding. (4) Only after log-implementation succeeds, mark the task complete by changing [-] to [x] in tasks.md._

- [ ] 10.2 Implement feature-specific components
  - Wire state + API integration via existing hooks.
  - _Leverage: src/hooks/useApi.ts, src/components/BaseComponent.tsx_
  - _Requirements: 5.2, 5.3_
  - _Prompt: Implement the task for spec {spec_name}: Role: React developer | Task: implement feature components wired to useApi (req 5.2, 5.3) | Restrictions: use existing state-management patterns; surface loading + error states; do not call the API outside the hook | Success: components handle loading/error correctly, data flow consistent with sibling features, UX responsive.

Before starting implementation: (1) mark this task as in_progress by changing [ ] to [-] in tasks.md. (2) Search existing Implementation Logs for reusable code under `.spec-workflow/impl-log/{spec_name}/`. After implementation and testing: (3) call `.spec-workflow/sdd util/log-implementation.py` to record what was done — this MUST succeed before proceeding. (4) Only after log-implementation succeeds, mark the task complete by changing [-] to [x] in tasks.md._

- [ ] 11. Plan integration approach
  - Define integration strategy + test coverage targets.
  - _Leverage: src/utils/integrationUtils.ts, tests/helpers/testUtils.ts_
  - _Requirements: 6.0_
  - _Prompt: Implement the task for spec {spec_name}: Role: integration engineer | Task: plan the integration approach (req 6.0) using integrationUtils.ts and the test helpers | Restrictions: account for every system component; preserve integration-test reliability; document coverage targets | Success: integration plan reviewed, system components mapped, coverage targets stated.

Before starting implementation: (1) mark this task as in_progress by changing [ ] to [-] in tasks.md. (2) Search existing Implementation Logs for reusable code under `.spec-workflow/impl-log/{spec_name}/`. After implementation and testing: (3) call `.spec-workflow/sdd util/log-implementation.py` to record what was done — this MUST succeed before proceeding. (4) Only after log-implementation succeeds, mark the task complete by changing [-] to [x] in tasks.md._

- [ ] 11.1 Write end-to-end tests
  - Set up the E2E framework + critical user-journey tests.
  - _Leverage: tests/helpers/testUtils.ts, tests/fixtures/data.ts_
  - _Requirements: All_
  - _Prompt: Implement the task for spec {spec_name}: Role: QA automation engineer | Task: implement E2E tests for the critical user journeys (all reqs) using the chosen framework | Restrictions: test real user workflows; keep tests maintainable; do not assert on implementation details | Success: critical journeys covered, tests run reliably in CI, journeys map to requirement IDs.

Before starting implementation: (1) mark this task as in_progress by changing [ ] to [-] in tasks.md. (2) Search existing Implementation Logs for reusable code under `.spec-workflow/impl-log/{spec_name}/`. After implementation and testing: (3) call `.spec-workflow/sdd util/log-implementation.py` to record what was done — this MUST succeed before proceeding. (4) Only after log-implementation succeeds, mark the task complete by changing [-] to [x] in tasks.md._

- [ ] 11.2 Final integration and cleanup
  - Integrate all components; finalise docs.
  - _Leverage: src/utils/cleanup.ts, docs/templates/_
  - _Requirements: All_
  - _Prompt: Implement the task for spec {spec_name}: Role: senior developer | Task: finish integration and clean up (all reqs) using cleanup.ts and the doc templates | Restrictions: do not break existing functionality; keep code-quality bars; preserve documentation consistency | Success: integration complete, lint and tests green, docs reflect the final state.

Before starting implementation: (1) mark this task as in_progress by changing [ ] to [-] in tasks.md. (2) Search existing Implementation Logs for reusable code under `.spec-workflow/impl-log/{spec_name}/`. After implementation and testing: (3) call `.spec-workflow/sdd util/log-implementation.py` to record what was done — this MUST succeed before proceeding. (4) Only after log-implementation succeeds, mark the task complete by changing [-] to [x] in tasks.md._
