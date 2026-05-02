# CS-014 Future Improvements — Minimal API Contract for List, Detail, Filter and Pagination

## Purpose

This document captures intentionally deferred improvements after the Sprint 4 task: **establish a minimal API contract for list/detail/filter/pagination**.

The implemented MVP scope should give RetailOps stable list responses with:

```json
{
  "items": [],
  "pagination": {
    "limit": 50,
    "offset": 0,
    "total": 0
  }
}
```

This is enough for frontend integration, API tests, OpenAPI visibility, and CI/CD confidence without overengineering the API too early.

---

## Current Scope Boundary

### Included now

- `GET /products`
- `GET /products/{product_id}`
- `GET /forecasts`
- `GET /forecasts/{forecast_id}`
- stable list response shape: `items` + `pagination`
- basic filters
- offset/limit pagination
- simple whitelisted sorting
- response models visible in OpenAPI
- minimal API contract tests using FastAPI `TestClient`
- reuse of existing repository/service/domain structure from Sprint 3

### Not included now

- write endpoints
- authentication / authorization / RBAC
- cursor-based pagination
- API versioning such as `/api/v1`
- generated API clients / SDKs
- strict OpenAPI snapshot testing
- advanced query language
- full product 360 aggregate endpoint
- nested joins for product sales, stock, forecasts, alerts and recommendations
- frontend consumption of all new endpoints
- observability metrics per endpoint
- rate limiting
- caching

---

## Recommended Future Implementation Order

### 1. Contract hardening

Add tests that validate OpenAPI schemas for the key endpoints.

Recommended next checks:

- `/openapi.json` contains `ProductListResponse` and `ForecastListResponse`,
- list endpoints always expose `items` and `pagination`,
- validation errors return a safe standard response,
- unknown route still returns the existing standard error contract.

### 2. Product 360 endpoint

Add a product detail view with related operational context.

Potential endpoint:

```text
GET /products/{product_id}/overview
```

Potential response sections:

- product master data,
- latest inventory snapshot,
- latest forecast,
- recent sales summary,
- active alerts,
- active recommendations.

This should be implemented only after the basic product and forecast endpoints are stable.

### 3. Inventory and alert list endpoints

Add endpoints for the next business-facing resources.

Suggested order:

```text
GET /inventory-snapshots
GET /alerts
GET /alerts/{alert_id}
GET /recommendations
GET /recommendations/{recommendation_id}
```

Keep the same `items` + `pagination` list response contract.

### 4. Frontend integration

Connect the React pages to the new API endpoints.

Suggested flow:

1. Products page consumes `GET /products`.
2. Forecasts page consumes `GET /forecasts`.
3. Dashboard cards link to product details.
4. Basic loading/error/empty states are added.

### 5. Observability and delivery evidence

Add lightweight API evidence after the endpoints are used by frontend or demo flows.

Possible evidence:

- smoke-test script for `/products` and `/forecasts`,
- response examples in docs,
- local demo screenshots,
- API latency measurement in a simple smoke test,
- CI log proving tests and Docker image build pass.

### 6. API versioning and compatibility policy

Introduce `/api/v1` only when there are enough endpoints or external consumers to justify it.

Before that, document a simple rule:

> Existing response keys should not be renamed or removed without updating tests and documentation.

### 7. Cursor pagination

Offset pagination is acceptable for MVP/demo data. Cursor pagination can be added later if lists become large or performance-sensitive.

Potential future contract:

```json
{
  "items": [],
  "pagination": {
    "limit": 50,
    "next_cursor": "opaque-token",
    "previous_cursor": null
  }
}
```

Do not add this before it is needed.

---

## ADR-Style Notes

### Decision 1: Offset pagination now, cursor pagination later

**Option A — Offset pagination now**

Pros:

- simple to implement,
- easy to test,
- easy for junior engineers to understand,
- enough for local MVP and seed data.

Cons:

- less efficient for very large datasets,
- can become unstable if data changes while a user pages through results.

**Option B — Cursor pagination now**

Pros:

- better for large production datasets,
- more stable for high-volume changing data.

Cons:

- more complex,
- premature for Sprint 4,
- harder to explain and test at the current maturity level.

**Chosen for now:** Offset pagination.

---

### Decision 2: Reusable response shape now, full API versioning later

**Chosen for now:** Keep endpoints simple and make the response contract stable through schemas and tests.

API versioning can be added later when RetailOps has more clients, environments, and backward-compatibility needs.

---

## Common Future Risks

- adding new list endpoints that return a raw array instead of `items` + `pagination`,
- mixing API response formatting into repositories,
- building complex joins directly inside route handlers,
- adding authentication before response contracts are stable,
- changing response key names without updating tests,
- exposing internal database errors to clients,
- allowing arbitrary `sort_by` values and creating SQL injection risk,
- expanding endpoint scope faster than tests and documentation.

---

## Future Definition of Done for API Contract Maturity

A more mature API contract will be ready when:

- all resource list endpoints use `items` + `pagination`,
- all detail endpoints return a single object or standard `404`,
- OpenAPI docs show concrete response schemas,
- contract tests cover positive, empty, invalid-query and not-found cases,
- frontend uses the stable API contract,
- CI blocks changes that break response shape,
- API documentation includes examples for all primary endpoints,
- security and observability additions do not break the public contract.
