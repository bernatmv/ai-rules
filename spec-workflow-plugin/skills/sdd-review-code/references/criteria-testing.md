# Testing Criteria

Evaluates test coverage, quality, and alignment with project testing conventions.

## Contents
- [Test Coverage Checks](#test-coverage-checks)
- [Integration Test Patterns](#integration-test-patterns)
- [Coverage Gap Methodology](#coverage-gap-methodology)

---

## Test Coverage Checks

| # | Criterion | Pass | Fail |
|---|-----------|------|------|
| 1 | **Unit test existence** | Tests exist for new public APIs; correct naming convention and location | No tests for new code; wrong location or naming |
| 2 | **Happy path coverage** | Normal operation tested; expected inputs produce expected outputs | Only error cases tested; missing primary functionality tests |
| 3 | **Error case coverage** | Error conditions tested; edge cases covered; invalid inputs handled | Only happy path; no error case tests; missing edge cases |
| 4 | **Test utility usage** | Existing utilities used per `_Leverage:`; mock patterns followed; fixtures reused | Custom mocks when generated exist; reinvented test utilities |
| 5 | **Test quality** | Deterministic; independent; clear assertions; AAA pattern | Flaky; order-dependent; missing/weak assertions; testing multiple things |

## Integration Test Patterns

| # | Criterion | Pass | Fail |
|---|-----------|------|------|
| 6 | **API endpoint testing** | HTTP routes tested with realistic request/response; status codes, headers, and body validated | No endpoint tests; only internal function tests for API code |
| 7 | **Database test isolation** | Each test uses transactions, fixtures, or a dedicated test DB; no shared mutable state between tests | Tests share a database without cleanup; ordering-dependent; flaky due to stale data |
| 8 | **Test environment setup** | CI-reproducible setup (Docker, in-memory DB, or documented seed); env vars documented | Tests rely on local-only services; undocumented environment prerequisites; CI failures |

## Coverage Gap Methodology

When evaluating test coverage:

1. **Identify public API surface** — list all new/modified public functions, methods, endpoints
2. **Map tests to API surface** — for each public function, verify at least one test exists
3. **Check branch coverage** — for conditionals (if/else, switch), verify both branches have tests
4. **Verify error paths** — for each try/catch or error return, verify error case tested
5. **Assess integration points** — where modules connect, verify integration tests exist

| Coverage Level | Threshold | Verdict |
|---------------|-----------|---------|
| Comprehensive | All 5 checks pass | Pass |
| Adequate | Checks 1-3 pass | Pass with suggestions |
| Insufficient | Check 1 or 2 fails | Fail |
