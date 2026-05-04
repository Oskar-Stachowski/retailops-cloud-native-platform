# RetailOps API Standards

This document defines REST API conventions, OpenAPI documentation rules, response contracts, testing expectations and error response patterns for the RetailOps Cloud-Native AI Platform.

The API is the backend entry point for product data, sales signals, inventory snapshots, stock-risk analysis, dashboard summaries, operational alerts and future recommendation workflows.

---

## 1. Current API Scope

### Platform endpoints

```text
GET /health
GET /ready
```

### Dashboard endpoints

```text
GET /dashboard/summary
GET /dashboard/operational-visibility?sales_trend_days=14&work_items_limit=10
GET /dashboard/sales-trend?days=14
GET /dashboard/alerts?limit=10
GET /dashboard/recommendations?limit=10
GET /dashboard/open-work-items?limit=10
GET /dashboard/stock-risk-summary
```

### Analytics endpoints

```text
GET /analytics/products?limit=50
GET /analytics/inventory-risk?limit=50
```

### Core resource endpoints

```text
GET /products
GET /products/{product_id}
GET /forecasts
GET /forecasts/{forecast_id}
GET /inventory-snapshots
GET /inventory-snapshots/{inventory_snapshot_id}
GET /sales
GET /sales/{sale_id}
GET /inventory-risks
```

The core resource endpoints are intended for stable frontend and integration usage. Dashboard and analytics endpoints are more presentation-oriented and may aggregate several tables into frontend-friendly response shapes.

---

## 2. CS-015 Dashboard Summary Contract

CS-015 exposes dashboard summary endpoints for operational visibility. The purpose is to give the frontend and demo reviewers one compact API surface for answering:

```text
What is happening in RetailOps right now?
```

Dashboard endpoints are intentionally read-only in the current scope.

### 2.1 Dashboard summary

```text
GET /dashboard/summary
```

Response shape:

```json
{
  "summary": {
    "products_count": 8,
    "sales_count": 120,
    "inventory_snapshots_count": 24,
    "forecasts_count": 32,
    "anomalies_count": 5,
    "recommendations_count": 6,
    "open_anomalies_count": 2,
    "open_recommendations_count": 3,
    "open_work_items_count": 5,
    "last_refresh_at": "2026-05-02T13:34:23Z"
  }
}
```

### 2.2 Operational visibility overview

```text
GET /dashboard/operational-visibility?sales_trend_days=14&work_items_limit=10
```

Response shape:

```json
{
  "generated_at": "2026-05-02T13:40:00Z",
  "summary": {},
  "stock_risk_summary": {},
  "sales_trend": [],
  "open_work_items": [],
  "limits": {
    "sales_trend_days": 14,
    "work_items_limit": 10
  }
}
```

This endpoint is intentionally presentation-oriented. It is not a replacement for stable core resource endpoints such as `/products`, `/sales` or `/inventory-risks`.

### 2.3 Sales trend

```text
GET /dashboard/sales-trend?days=14
```

Response shape:

```json
{
  "items": [
    {
      "date": "2026-05-01",
      "units_sold": 42.0,
      "revenue": 4200.5
    }
  ],
  "days": 14
}
```

### 2.4 Open work items

```text
GET /dashboard/open-work-items?limit=10
```

Response shape:

```json
{
  "items": [
    {
      "id": "work-item-1",
      "source": "anomaly",
      "product_id": "85710dbe-1aea-50ac-a155-fb216e12ab97",
      "sku": "ELEC-HEAD-001",
      "type": "sales_drop",
      "severity": "medium",
      "priority": null,
      "status": "open",
      "title": null,
      "description": "Sales dropped below expected level.",
      "created_at": "2026-05-01T10:00:00Z",
      "updated_at": null,
      "detected_at": "2026-05-01T09:30:00Z"
    }
  ],
  "limit": 10
}
```

Open work items may combine open anomalies, open recommendations and future operational tasks into one dashboard-friendly feed.

### 2.5 Stock-risk summary

```text
GET /dashboard/stock-risk-summary
```

Response shape:

```json
{
  "total_risk_items": 8,
  "normal_count": 4,
  "stockout_risk_count": 2,
  "overstock_risk_count": 1,
  "unknown_count": 1
}
```

---

## 3. REST API Conventions

Use lowercase, plural nouns for business resources.

Recommended examples:

```text
GET /products
GET /sales
GET /inventory-snapshots
GET /inventory-risks
GET /alerts
GET /recommendations
```

Avoid verbs in endpoint paths.

Prefer:

```text
GET /alerts
```

Instead of:

```text
GET /getAlerts
```

Dashboard paths may use descriptive nouns when they represent frontend widgets or summaries.

Acceptable examples:

```text
GET /dashboard/summary
GET /dashboard/sales-trend
GET /dashboard/open-work-items
GET /dashboard/stock-risk-summary
```

---

## 4. HTTP Methods

| Method | Purpose |
|---|---|
| GET | Read data |
| POST | Create a resource or trigger a controlled operation |
| PUT | Replace a resource |
| PATCH | Partially update a resource |
| DELETE | Delete a resource |

Current Sprint 4 API scope uses read-only `GET` endpoints only.

---

## 5. Status Codes

| Status code | Meaning |
|---|---|
| 200 OK | Successful read or health check |
| 201 Created | Resource created |
| 204 No Content | Successful action with no response body |
| 400 Bad Request | Invalid request |
| 401 Unauthorized | Missing or invalid authentication |
| 403 Forbidden | Authenticated user lacks required permission |
| 404 Not Found | Resource or endpoint not found |
| 409 Conflict | Resource conflict |
| 422 Unprocessable Entity | Validation error |
| 500 Internal Server Error | Unexpected server error |

---

## 6. Response Conventions

### 6.1 Detail response

Detail endpoints return the resource directly.

Example:

```json
{
  "id": "85710dbe-1aea-50ac-a155-fb216e12ab97",
  "sku": "ELEC-HEAD-001",
  "name": "Wireless Headphones",
  "category": "Electronics",
  "brand": "SoundWave",
  "status": "active"
}
```

### 6.2 List response

All stable resource list endpoints return a top-level `items` key and `pagination` metadata.

Example:

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

Do not return a raw JSON array from stable resource list endpoints.

Dashboard endpoints may use widget-specific response shapes when a classic list contract would make the frontend less clear.

### 6.3 Pagination

Current MVP pagination uses:

```text
limit
offset
total
```

Current limits:

```text
limit: 1..100
offset: >= 0
```

Cursor pagination is intentionally deferred.

---

## 7. Current Core Endpoint Examples

### Products

```text
GET /products?limit=5&offset=0
GET /products?category=Electronics&status=active&search=head&sort_by=sku&sort_order=asc
GET /products/{product_id}
```

### Forecasts

```text
GET /forecasts?limit=5&offset=0
GET /forecasts?product_id={product_id}&status=generated&method=seeded_demo
GET /forecasts/{forecast_id}
```

### Inventory snapshots

```text
GET /inventory-snapshots?limit=5&offset=0
GET /inventory-snapshots?product_id={product_id}&warehouse_code=WH-001&unit_of_measure=pcs
GET /inventory-snapshots/{inventory_snapshot_id}
```

### Sales

```text
GET /sales?limit=5&offset=0
GET /sales?product_id={product_id}&channel=online&currency=PLN
GET /sales/{sale_id}
```

### Stock risk

```text
GET /inventory-risks?limit=5&offset=0
GET /inventory-risks?risk_status=stockout_risk
GET /inventory-risks?category=Electronics
```

---

## 8. Error Response Pattern

All controlled API errors should follow one normalized JSON structure.

```json
{
  "error": {
    "code": "not_found",
    "message": "Resource not found"
  }
}
```

The `code` field should be stable and machine-readable. The `message` field should be human-readable and safe to expose.

Do not expose:

- stack traces,
- internal exception class names,
- credentials,
- database connection details,
- infrastructure identifiers,
- cloud account details.

---

## 9. OpenAPI Documentation Rules

FastAPI automatically exposes OpenAPI documentation.

Local URLs:

```text
GET /docs
GET /openapi.json
```

Each public endpoint should define:

- clear path,
- correct HTTP method,
- tag,
- summary,
- description,
- response model where practical,
- typed query parameters,
- typed path parameters,
- documented response status codes where useful.

Recommended tags:

```text
health
dashboard
analytics
products
forecasts
inventory
sales
stock-risk
alerts
recommendations
admin
```

---

## 10. Testing Expectations

Each new endpoint should include at least one automated contract test.

Current minimum API contract tests:

```text
GET /products returns items + pagination
GET /products/{product_id} returns detail or standard 404
GET /forecasts returns items + pagination
GET /forecasts/{forecast_id} returns detail or standard 404
GET /inventory-snapshots returns items + pagination
GET /inventory-snapshots/{inventory_snapshot_id} returns detail or standard 404
GET /sales returns items + pagination
GET /sales/{sale_id} returns detail or standard 404
GET /inventory-risks returns items + pagination
GET /dashboard/summary returns summary object
GET /dashboard/operational-visibility returns summary, stock risk, sales trend and open work items
GET /dashboard/sales-trend returns items
GET /dashboard/open-work-items returns items
GET /dashboard/stock-risk-summary returns stock-risk counters
```

Tests should verify:

- HTTP status code,
- response JSON shape,
- key business fields or error fields,
- pagination metadata for stable resource list endpoints,
- safe error response structure,
- absence of unstable assumptions where possible.

Tests should be runnable locally with:

```bash
pytest
```

The GitHub Actions pipeline should fail if API tests fail.

---

## 11. CI/CD Expectations

The API CI workflow should validate at least:

```text
install dependencies
run pytest
build Docker image
```

A failed test or failed Docker build should block the change.

The API CI workflow should run when relevant API, data or workflow files change.

Recommended trigger areas:

```text
services/api/**
data/**
.github/workflows/api-ci.yml
```

---

## 12. Security Expectations

The API should follow secure-by-default conventions:

- do not expose secrets in responses,
- do not expose stack traces to clients,
- keep error messages safe and minimal,
- validate request inputs,
- avoid leaking infrastructure details,
- whitelist sort fields,
- prepare future endpoints for authentication and RBAC.

Authentication and RBAC are intentionally not implemented in the current Sprint 4 scope.

---

## 13. Observability Expectations

The `/health` and `/ready` endpoints support:

- local smoke checks,
- Docker health checks,
- future Kubernetes probes,
- future uptime checks,
- API availability SLI.

Dashboard summary endpoints support operational visibility for demo and frontend use cases.

Future production observability may add:

- request logs,
- structured logging,
- metrics endpoint,
- tracing,
- correlation/request IDs,
- OpenTelemetry integration,
- Prometheus/Grafana dashboards.

These are not required for the current Sprint 4 implementation, but the current conventions should allow them to be added later.

---

## 14. Scope Boundary

### Included now

- read-only health and readiness endpoints,
- dashboard summary and operational visibility endpoints,
- analytics read endpoints,
- stable core APIs for products, forecasts, inventory snapshots, sales and inventory risks,
- consistent error responses,
- OpenAPI response models,
- pytest contract tests,
- CI validation for tests and Docker image builds.

### Deferred

- authentication / authorization / RBAC,
- write endpoints,
- `/api/v1` versioning,
- cursor pagination,
- frontend integration for every dashboard widget,
- OpenAPI snapshot testing,
- rate limiting,
- caching,
- orders API,
- generated SDKs,
- production deployment.
