# Performance Criteria

Evaluates algorithmic efficiency, database access patterns, caching, resource management, and rendering performance.

## Contents
- [Algorithmic Efficiency](#algorithmic-efficiency)
- [Database Access](#database-access)
- [Caching](#caching)
- [Bundle and Assets](#bundle-and-assets)
- [Concurrency](#concurrency)
- [Memory Management](#memory-management)
- [Observability](#observability)
- [Rendering Performance](#rendering-performance)

---

## Algorithmic Efficiency

| # | Check | Pass | Fail |
|---|-------|------|------|
| 1 | **Complexity** | Appropriate complexity for the problem; efficient data structures | O(n²) when O(n) possible; repeated cacheable lookups |
| 2 | **Nested loops** | Nested iterations justified; inner loops bounded | Unnecessary nesting; quadratic behavior on large datasets |
| 3 | **Hot path identification** | Frequently-called code paths optimized | Performance-critical paths use expensive operations |

## Database Access

| # | Check | Pass | Fail |
|---|-------|------|------|
| 4 | **N+1 query detection** | Related data fetched in batch/join; no loops issuing individual queries | Loop fetching related records one-by-one; lazy loading in iteration |
| 5 | **Unbounded queries** | Queries use LIMIT/pagination; result sets bounded | SELECT without LIMIT on potentially large tables |
| 6 | **Index usage** | Queries filter on indexed columns; new queries have appropriate indexes | Full table scans on large tables; missing indexes for frequent queries |

## Caching

| # | Check | Pass | Fail |
|---|-------|------|------|
| 7 | **Cacheable computation** | Expensive computations cached when inputs are stable | Same expensive computation repeated with identical inputs |
| 8 | **Redundant API calls** | API responses cached where appropriate; no duplicate fetches | Same endpoint called multiple times in a single flow |
| 9 | **Memoization** | Pure functions with expensive computation are memoized | Missing memoization on frequently-called pure functions |

## Bundle and Assets

| # | Check | Pass | Fail |
|---|-------|------|------|
| 10 | **Large imports** | Tree-shakeable imports; no full-library imports for single functions | `import * from large-lib` when only one function needed |
| 11 | **Tree-shaking blockers** | Side-effect-free modules; barrel exports don't prevent tree-shaking | Side effects in module scope; barrel files re-export everything |

## Concurrency

| # | Check | Pass | Fail |
|---|-------|------|------|
| 12 | **Async/await usage** | Long-running ops async; main thread unblocked; proper cancellation | Synchronous network calls; blocking main thread; leaked tasks |
| 13 | **Parallelization** | Independent async operations run concurrently (Promise.all, Task groups) | Sequential await on independent operations |
| 14 | **Deadlock patterns** | No circular lock dependencies; consistent lock ordering | Potential deadlocks from inconsistent lock acquisition |

## Memory Management

| # | Check | Pass | Fail |
|---|-------|------|------|
| 15 | **Leak detection** | No obvious leaks; appropriate weak/unowned refs; large allocations managed | Strong reference cycles; closures capturing self strongly |
| 16 | **Unbounded collections** | Collections have size limits or eviction; growth bounded | Maps/arrays that grow without bound; no eviction policy |
| 17 | **Event listener cleanup** | Listeners removed on teardown; subscriptions unsubscribed | Listeners accumulate; subscriptions never cleaned up |

## Observability

| # | Check | Pass | Fail |
|---|-------|------|------|
| 18 | **Structured logging in critical paths** | Key operations (auth, payments, data mutations) emit structured log entries with correlation IDs | Critical paths have no logging or use unstructured print/console statements |
| 19 | **Metrics emission** | Latency, error rate, and throughput metrics emitted for external calls and key endpoints | No metrics; unable to detect degradation without manual inspection |
| 20 | **Tracing propagation** | Trace context (OpenTelemetry / X-Ray / similar) propagated across service boundaries | Traces broken at service boundaries; no span context forwarded |

## Rendering Performance

| # | Check | Pass | Fail |
|---|-------|------|------|
| 21 | **Unnecessary re-renders** | Render triggers are specific; memoization used where appropriate | Component re-renders on every parent render; missing React.memo/useMemo |
| 22 | **Prop drilling** | State accessed via context or state management where appropriate | Deep prop chains causing unnecessary intermediate re-renders |
| 23 | **Virtualization** | Long lists use virtualization (virtual scroll, windowing) | Rendering thousands of DOM elements without virtualization |
