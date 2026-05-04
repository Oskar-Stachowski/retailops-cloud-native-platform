# Sprint 4 Future Improvements — API Integration Tests

## Purpose

This document captures intentionally deferred improvements after adding Sprint 4 integration tests for the main RetailOps API listings, detail endpoints and filters.

The current test scope proves that the real application path works end-to-end:

```text
FastAPI endpoint
  -> service layer
  -> repository/query layer
  -> PostgreSQL
  -> seeded demo data
  -> JSON response contract
```

This complements the existing contract tests. Contract tests validate API shape quickly. Integration tests validate that the real runtime path does not break because of SQL, schema, seed-data or serialization mismatches.

---

## Current Scope Boundary

### Included now

- Integration coverage for core Sprint 4 list endpoints:
  - `GET /products`
  - `GET /forecasts`
  - `GET /inventory-snapshots`
  - `GET /sales`
  - `GET /inventory-risks`
- Detail endpoint round-trip checks for resources that have detail routes:
  - `GET /products/{product_id}`
  - `GET /forecasts/{forecast_id}`
  - `GET /inventory-snapshots/{inventory_snapshot_id}`
  - `GET /sales/{sale_id}`
- Basic filter checks using values discovered from seeded data.
- Basic pagination contract checks: `items`, `pagination.limit`, `pagination.offset`, `pagination.total`.
- Basic sort validation for allowed and rejected sort fields.
- 404 checks for missing detail resources.
- 422 checks for invalid pagination and invalid sort parameters.

### Not included now

- Write endpoint integration tests.
- Auth/RBAC integration tests.
- Frontend-to-API E2E tests.
- Browser automation with Playwright/Cypress.
- OpenAPI snapshot testing.
- Performance/load tests.
- Testcontainers-based disposable PostgreSQL.
- Per-test isolated database schema.
- Automatic seed generation inside each test case.
- CI artifact publication for integration-test evidence.
- Full dashboard integration coverage.

---

## Recommended Future Implementation Order

### 1. Add a dedicated integration-test CI job

The current API CI can run all tests in one job. Later, split test stages:

```text
unit / contract tests
  -> integration tests with PostgreSQL
  -> Docker image build
  -> smoke tests against containerized API
```

This makes failures easier to diagnose.

### 2. Add explicit pytest markers

Introduce markers such as:

```ini
markers =
    integration: tests requiring PostgreSQL and seeded data
    contract: fast API contract tests using TestClient and fake services
```

Then CI can run:

```bash
pytest -m "not integration"
pytest -m integration
```

### 3. Make database setup deterministic per test run

Future options:

- run Alembic migrations before integration tests,
- load seed data in a session fixture,
- use a separate test database,
- truncate and reseed controlled tables before integration tests,
- isolate test data with a unique run identifier.

This will reduce dependence on developer-local database state.

### 4. Add Testcontainers or disposable PostgreSQL

For stronger repeatability, use Testcontainers or Docker Compose test services so each integration run starts from a clean PostgreSQL instance.

This is more robust but adds setup complexity, so it is intentionally deferred.

### 5. Add OpenAPI compatibility tests

Add tests that verify public response schemas do not accidentally lose key fields:

- `items`,
- `pagination`,
- resource identifiers,
- filter query parameters,
- response models.

This protects frontend integration and external clients.

### 6. Add dashboard integration tests

After dashboard endpoints stabilize, add integration checks for:

- `GET /dashboard/summary`,
- `GET /dashboard/operational-visibility`,
- `GET /dashboard/sales-trend`,
- `GET /dashboard/open-work-items`,
- `GET /dashboard/stock-risk-summary`.

These should validate that dashboard aggregates remain compatible with seeded data.

### 7. Add smoke-test scripts for release evidence

Create a simple script such as:

```text
scripts/smoke_api.sh
```

It should call the core endpoints with `curl` and fail on non-2xx responses. This can be reused locally, in CI and in future Kubernetes readiness validation.

---

## ADR-Style Notes

### Decision 1: Integration tests use real FastAPI app and PostgreSQL

**Chosen now:** exercise the real app through `TestClient`, with no service/repository monkeypatching.

Rationale:

- catches SQL/schema/runtime mismatches,
- prevents green contract tests from hiding database failures,
- matches the failure mode seen in the `/sales` endpoint,
- remains faster than full browser E2E tests.

### Decision 2: Use seeded demo data instead of hardcoded insert fixtures

**Chosen now:** derive filter values from seeded rows returned by the API.

Rationale:

- avoids duplicating seed rules inside tests,
- keeps tests aligned with existing demo-data strategy,
- reduces setup code,
- stays fast for Sprint 4.

Trade-off:

- tests depend on the database being migrated and seeded before execution.

### Decision 3: Keep one compact integration test file

**Chosen now:** one file: `test_core_api_integration.py`.

Rationale:

- easy to copy and run,
- minimal file churn,
- clear Sprint 4 boundary,
- enough evidence for the current task.

Future split can happen when endpoint groups grow.

---

## Common Future Risks

- Treating contract tests as integration tests.
- Letting integration tests rely on accidental local database state.
- Adding brittle assertions against exact row counts from seed data.
- Forgetting to run migrations before tests.
- Forgetting to seed demo data before tests.
- Allowing `/sales`-style SQL/schema mismatches to pass because repository paths are mocked.
- Making integration tests too slow and discouraging developers from running them locally.
- Mixing browser E2E scope into API integration scope too early.

---

## Suggested Evidence to Capture

For portfolio and delivery evidence, capture:

```text
pytest tests/test_core_api_integration.py
make test
GitHub Actions green run
curl smoke checks for the same endpoints
```

Recommended PR note:

```text
Added integration tests for Sprint 4 core API endpoints.
The tests exercise FastAPI -> service -> repository -> PostgreSQL using seeded demo data.
They cover list responses, detail responses, filters, pagination, invalid query validation and 404 behavior.
```
