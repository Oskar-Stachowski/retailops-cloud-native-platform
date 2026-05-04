# CS-015 Future Improvements — Dashboard Summary and Operational Visibility

## Purpose

This document captures intentionally deferred improvements after Sprint 4 task **CS-015: Expose dashboard summary endpoints for operational visibility**.

The implemented MVP scope gives RetailOps a read-only dashboard API layer for answering operational questions quickly:

```text
Products + Sales + Inventory + Forecasts + Anomalies + Recommendations
        -> Dashboard Summary
        -> Operational Visibility
        -> Frontend / Demo Evidence
```

The goal is not to build a complete BI platform yet. The goal is to expose a stable, testable and frontend-friendly set of dashboard endpoints that can support the first operational dashboard.

<p align="center">
  <img src="images/cs-015-dashboard-summary-endpoints.png" width="90%"/>
</p>
<p align="center"><em>Figure: CS-015 Dashboard Summary Endpoints for Operational Visibility</em></p>

---

## Current Scope Boundary

### Included now

- `GET /dashboard/summary`
- `GET /dashboard/operational-visibility`
- `GET /dashboard/sales-trend`
- `GET /dashboard/alerts`
- `GET /dashboard/recommendations`
- `GET /dashboard/open-work-items`
- `GET /dashboard/stock-risk-summary`
- read-only dashboard API surface
- service layer that normalizes dashboard responses
- repository layer that keeps SQL outside FastAPI route handlers
- response models visible in OpenAPI
- minimal API contract tests using FastAPI `TestClient`
- compatibility with existing Sprint 3 dashboard endpoint names

### Not included now

- frontend dashboard wiring
- authentication / authorization / RBAC
- user-specific dashboard personalization
- saved dashboard layouts
- write actions on alerts or recommendations
- real-time updates or WebSockets
- caching layer
- BI-grade analytical model
- materialized views
- historical KPI snapshots
- SLO dashboards in Grafana
- end-to-end browser tests

---

## Recommended Future Implementation Order

### 1. Runtime smoke evidence

After tests pass, capture runtime checks for:

```text
GET /health
GET /ready
GET /dashboard/summary
GET /dashboard/operational-visibility?sales_trend_days=14&work_items_limit=10
GET /dashboard/sales-trend?days=14
GET /dashboard/open-work-items?limit=10
GET /dashboard/stock-risk-summary
```

Recommended evidence:

- terminal output,
- screenshot of Swagger UI,
- short PR/commit note,
- green GitHub Actions run.

### 2. Frontend integration

Connect the dashboard page to the new backend endpoints.

Recommended sequence:

1. Render `/dashboard/summary` as KPI cards.
2. Render `/dashboard/sales-trend` as a simple chart or table.
3. Render `/dashboard/open-work-items` as an operations backlog widget.
4. Render `/dashboard/stock-risk-summary` as stock-risk cards.
5. Add loading and error states.

### 3. Contract hardening

Add stronger contract checks around the dashboard API.

Recommended tests:

- `/openapi.json` contains dashboard response models,
- invalid query params return `422`,
- dashboard endpoints do not return raw SQL shapes,
- timestamps are JSON-safe,
- empty database returns valid zero/empty responses rather than `500`.

### 4. Runtime integration tests

Current contract tests can use fake services to stay fast. Later, add a small integration test path that uses a seeded PostgreSQL database.

Recommended checks:

- `/dashboard/summary` reads seeded row counts,
- `/dashboard/sales-trend` aggregates seeded sales,
- `/dashboard/stock-risk-summary` computes expected risk counts,
- `/dashboard/operational-visibility` combines all widgets into one stable payload.

### 5. Observability evidence

Add basic operational visibility for the dashboard API itself.

Future evidence ideas:

- request count per dashboard endpoint,
- latency per dashboard endpoint,
- error count per endpoint,
- smoke test status,
- dashboard API examples in documentation,
- later: Prometheus/Grafana panels.

### 6. Dashboard performance maturity

If dashboard queries become heavier, introduce performance controls in this order:

1. SQL indexes for dashboard query patterns.
2. Query-level optimizations.
3. Materialized views for summary widgets.
4. Short-lived application cache.
5. Async refresh or scheduled pre-computation.

Do not add caching before the query behavior is stable and measurable.

---

## Dashboard API Design Notes

### Why dashboard endpoints are separate from core resource endpoints

Core resource endpoints answer questions like:

```text
Show me sales records.
Show me product details.
Show me inventory snapshots.
```

Dashboard endpoints answer business-operational questions like:

```text
How many work items are open?
Are we seeing stock risk?
What is the recent sales trend?
Is the platform ready for an operations dashboard?
```

This separation keeps the API maintainable:

- core endpoints stay resource-oriented,
- dashboard endpoints stay presentation-oriented,
- frontend can use compact payloads,
- SQL stays in repositories,
- business response shaping stays in services.

---

## Future Endpoint Candidates

Potential dashboard endpoints:

```text
GET /dashboard/kpis
GET /dashboard/inventory-health
GET /dashboard/sales-health
GET /dashboard/forecast-quality
GET /dashboard/data-freshness
GET /dashboard/platform-readiness
```

Potential product-specific dashboard endpoint:

```text
GET /products/{product_id}/overview
```

Potential response sections:

- product master data,
- latest inventory snapshot,
- recent sales summary,
- latest forecast,
- current stock risk,
- open anomalies,
- open recommendations.

---

## Risks to Watch

### Risk 1: Dashboard endpoints become a hidden data warehouse

Avoid putting every business calculation into one massive endpoint. Keep MVP dashboard responses small and explicit.

### Risk 2: Frontend depends on unstable internal SQL field names

Always normalize responses in the service layer. Do not expose raw query rows directly when the row shape is unstable.

### Risk 3: Contract tests pass but runtime SQL fails

Fast API contract tests are useful, but they do not replace Docker Compose smoke checks against PostgreSQL.

### Risk 4: Too many dashboard variants too early

Do not create many dashboard endpoints before the first dashboard UI actually consumes them.

---

## Recommended Definition of Done for Future Dashboard Work

A future dashboard API task should be considered done when:

- endpoint response model is visible in OpenAPI,
- service method exists and normalizes the response,
- repository method keeps SQL isolated,
- tests validate response shape,
- Docker Compose smoke check passes,
- documentation includes endpoint purpose and example response,
- frontend usage is either implemented or explicitly deferred.
