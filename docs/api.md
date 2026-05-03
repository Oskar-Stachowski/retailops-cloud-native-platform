# RetailOps API Standards

This document defines REST API conventions, OpenAPI documentation rules, and error response patterns for the RetailOps Cloud-Native AI Platform.

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
GET /dashboard/sales-trend?days=14
GET /dashboard/alerts?limit=10
GET /dashboard/recommendations?limit=10
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

The core resource endpoints are intended for stable frontend and integration usage. Dashboard and analytics endpoints may remain more presentation-oriented.

---

## 2. REST API Conventions

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

---

## 3. HTTP Methods

| Method | Purpose |
|---|---|
| GET | Read data |
| POST | Create a resource or trigger a controlled operation |
| PUT | Replace a resource |
| PATCH | Partially update a resource |
| DELETE | Delete a resource |

Current CS-014 scope uses read-only `GET` endpoints only.

---

## 4. Status Codes

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

## 5. Response Conventions

### 5.1 Detail response

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

### 5.2 List response

All stable resource list endpoints must return a top-level object with `items` and `pagination`.

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

### 5.3 Pagination

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

## 6. Current Core Endpoint Examples

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

## 7. Error Response Pattern

All controlled API errors should follow one JSON structure.

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

## 8. OpenAPI Documentation Rules

FastAPI automatically exposes OpenAPI documentation.

Local URLs:

```text
http://localhost:8000/docs
http://localhost:8000/openapi.json
```

Each endpoint should have:

- clear path,
- correct HTTP method,
- tag,
- summary,
- response model where practical,
- documented response status codes.

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

## 9. Testing Expectations

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
```

Tests should verify:

- HTTP status code,
- response JSON shape,
- key business fields or error fields,
- absence of unstable assumptions where possible.

Tests should be runnable locally with:

```bash
pytest
```

The GitHub Actions pipeline should fail if API tests fail.

---

## 10. CI/CD Expectations

The API CI workflow should validate at least:

```text
install dependencies
run pytest
build Docker image
```

A failed test or failed Docker build should block the change.

---

## 11. Security Expectations

The API should follow secure-by-default conventions:

- do not expose secrets in responses,
- do not expose stack traces to clients,
- keep error messages safe and minimal,
- validate request inputs,
- avoid leaking infrastructure details,
- whitelist sort fields,
- prepare future endpoints for authentication and RBAC.

Authentication and RBAC are intentionally not implemented in CS-014.

---

## 12. Observability Expectations

The `/health` and `/ready` endpoints support:

- local smoke checks,
- Docker health checks,
- future Kubernetes probes,
- future uptime checks,
- API availability SLI.

Future production observability may add:

- request logs,
- structured logging,
- metrics endpoint,
- tracing,
- correlation/request IDs.

These are not required for CS-014, but the current conventions should allow them to be added later.

---

## 13. MVP Boundary

Current CS-014 scope intentionally does not implement:

- authentication and RBAC,
- write endpoints,
- cursor pagination,
- advanced cross-resource filtering,
- nested product 360 responses,
- generated SDKs,
- full OpenAPI contract testing,
- production deployment.

These capabilities should be added later when the API surface and frontend usage justify the extra complexity.