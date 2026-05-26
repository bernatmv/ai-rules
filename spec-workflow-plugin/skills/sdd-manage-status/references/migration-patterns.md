# Migration Patterns

Patterns for generating tasks when design changes involve technology or architecture migrations.

## Progressive Migration Strategy

When a design change introduces a migration (e.g., database swap, API protocol change, framework upgrade), tasks should follow a progressive pattern that minimizes risk:

| Phase | Pattern | Purpose |
|-------|---------|---------|
| 1. Abstraction | Create adapter/interface layer | Decouple from old implementation |
| 2. New Implementation | Build new behind feature flag/adapter | Implement without disrupting existing |
| 3. Migration | Gradually switch traffic/data | Controlled rollout |
| 4. Cleanup | Remove old implementation | Reduce technical debt |

Each phase should be its own task or task group.

---

## Example: MongoDB → PostgreSQL Migration

### Task Structure

```markdown
- [ ] 4. Create database adapter interface
  _Leverage: existing MongoDB models, design.md § Data Layer
  _Requirements: REQ-4.1, REQ-4.2
  _Prompt: _Role: Database architect. Task: Create a DatabaseAdapter interface that abstracts all data operations currently using MongoDB directly. Map each MongoDB-specific call to a generic method. Restrictions: Do not modify existing MongoDB code — create a parallel interface. Success: All existing data operations have adapter methods, existing tests still pass._

- [ ] 5. Implement PostgreSQL adapter
  _Leverage: database adapter interface (task 4), design.md § PostgreSQL Schema
  _Requirements: REQ-4.3
  _Prompt: _Role: PostgreSQL specialist. Task: Implement the DatabaseAdapter interface for PostgreSQL. Create migrations, connection pooling, and all adapter methods. Restrictions: Do not remove MongoDB adapter. Success: PostgreSQL adapter passes all adapter interface tests._

- [ ] 6. Add migration tooling and data sync
  _Leverage: both adapters (tasks 4-5), design.md § Migration Strategy
  _Requirements: REQ-4.4
  _Prompt: _Role: Data migration engineer. Task: Create migration scripts and a dual-write mechanism. Both databases should receive writes during migration. Restrictions: Must be reversible — include rollback scripts. Success: Data can be migrated without downtime, rollback tested._

- [ ] 7. Switch primary database and cleanup
  _Leverage: migration tooling (task 6), design.md § Cutover Plan
  _Requirements: REQ-4.5
  _Prompt: _Role: DevOps engineer. Task: Switch primary reads to PostgreSQL, verify data integrity, then remove MongoDB adapter and dependencies. Restrictions: Keep MongoDB adapter for 1 release cycle as fallback. Success: All operations use PostgreSQL, no data loss verified._
```

---

## Example: REST → GraphQL Migration

### Task Structure

```markdown
- [ ] 8. Create GraphQL schema from existing REST endpoints
  _Leverage: existing route handlers, design.md § GraphQL Schema
  _Requirements: REQ-5.1
  _Prompt: _Role: GraphQL architect. Task: Define GraphQL types and resolvers that mirror existing REST endpoints. Restrictions: REST endpoints must continue working — GraphQL is additive. Success: GraphQL schema serves same data as REST, both work simultaneously._

- [ ] 9. Migrate frontend to GraphQL queries
  _Leverage: GraphQL schema (task 8), design.md § Client Migration
  _Requirements: REQ-5.2
  _Prompt: _Role: Frontend developer. Task: Progressively replace REST API calls with GraphQL queries in frontend components. Restrictions: One component at a time, feature-flag each migration. Success: All frontend data fetching uses GraphQL, REST endpoints still available._

- [ ] 10. Deprecate and remove REST endpoints
  _Leverage: GraphQL migration (task 9), design.md § API Deprecation
  _Requirements: REQ-5.3
  _Prompt: _Role: API architect. Task: Add deprecation headers to REST endpoints, monitor for remaining consumers, then remove after grace period. Restrictions: Log all REST usage for 2 weeks before removal. Success: REST endpoints removed, no client errors._
```

---

## Migration Task Format

When generating migration tasks, ensure:

| Field | Requirement |
|-------|-------------|
| _Leverage | References BOTH old and new technology artifacts |
| _Requirements | Maps to design.md migration sections |
| _Prompt → Restrictions | Explicitly states what NOT to break during migration |
| _Prompt → Success | Includes "existing functionality still works" criteria |
| Task ordering | Progressive: abstract → implement → migrate → cleanup |

Migration tasks should always include rollback considerations in the Restrictions section.
