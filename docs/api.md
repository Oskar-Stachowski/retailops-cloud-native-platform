# RetailOps API Standards

This document defines the initial REST API conventions, OpenAPI documentation rules, and error response pattern for the RetailOps Cloud-Native AI Platform.

The goal of this document is to keep future API development consistent, testable, and easy to integrate with frontend, CI/CD, observability, and security workflows.

---

## 1. Purpose

The RetailOps API is the backend entry point for future platform capabilities such as:

- product and category data access,
- inventory and stock-risk analysis,
- sales anomaly detection,
- dashboard summaries,
- operational alerts,
- recommendation and ML-driven decision support.

At the current MVP stage, the API exposes only a health endpoint.

---

## 2. Current API scope

Current implemented endpoint:

```text
GET /health
```

The endpoint is used for:

- local verification,
- automated tests,
- Docker health checks,
- CI validation,
- future Kubernetes liveness/readiness probes,
- basic API availability monitoring.

Out of scope for this stage:

- product APIs,
- inventory APIs,
- authentication and authorization,
- database integration,
- role-based access control,
- ML prediction endpoints,
- event-driven APIs,
- production deployment.

---

## 3. REST API conventions

### 3.1 Resource naming

Use lowercase, plural nouns for business resources.

Recommended future examples:

```text
GET /products
GET /products/{product_id}
GET /categories
GET /alerts
GET /inventory-risks
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

Actions that are not simple CRUD should still be modeled clearly and consistently.

Example future option:

```text
POST /recommendations/pricing
```

---

### 3.2 HTTP methods

Use HTTP methods according to their standard meaning:

| Method | Purpose |
|---|---|
| GET | Read data |
| POST | Create a resource or trigger a controlled operation |
| PUT | Replace a resource |
| PATCH | Partially update a resource |
| DELETE | Delete a resource |

Current MVP endpoint:

```text
GET /health
```

---

### 3.3 Status codes

Use predictable HTTP status codes.

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

For the current `/health` endpoint, the expected status is:

```text
200 OK
```

---

## 4. Response conventions

### 4.1 Health response

The `/health` endpoint should return a stable JSON object.

Example:

```json
{
  "status": "ok",
  "service": "retailops-api",
  "environment": "local"
}
```

This response should not include sensitive infrastructure details, secrets, hostnames, database credentials, cloud account identifiers, or internal network information.

---

### 4.2 Future success response pattern

For simple resource reads, future endpoints may return the resource directly.

Example:

```json
{
  "id": "SKU-001",
  "name": "Example Product",
  "category": "Beverages"
}
```

For list responses, use a stable top-level key.

Example:

```json
{
  "items": [
    {
      "id": "SKU-001",
      "name": "Example Product"
    }
  ]
}
```

Future pagination should use explicit metadata.

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

---

## 5. Error response pattern

All controlled API errors should follow one JSON structure.

Recommended standard:

```json
{
  "error": {
    "code": "not_found",
    "message": "Resource not found"
  }
}
```

The `code` field should be stable and machine-readable.

The `message` field should be human-readable and safe to expose.

Do not expose:

- stack traces,
- internal exception class names,
- credentials,
- database connection details,
- infrastructure identifiers,
- cloud account details.

---

### 5.1 Example: 404 Not Found

```json
{
  "error": {
    "code": "not_found",
    "message": "The requested resource was not found."
  }
}
```

---

### 5.2 Example: validation error

Future validation errors should be explicit and safe.

Example:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed."
  }
}
```

Detailed validation fields may be added later if needed, but they should remain consistent and safe for clients.

---

### 5.3 Example: internal server error

```json
{
  "error": {
    "code": "internal_server_error",
    "message": "An unexpected server error occurred."
  }
}
```

Internal details should be logged server-side, not returned to API clients.

---

## 6. OpenAPI documentation rules

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

For `/health`, OpenAPI should show a concrete response schema, not a generic dictionary with `additionalProp1`.

Recommended endpoint tag:

```text
health
```

Recommended future tags:

```text
products
inventory
alerts
analytics
ml
admin
```

---

## 7. Testing expectations

Each new endpoint should include at least one automated test.

Current minimum tests:

```text
GET /health returns 200
GET /health returns status = ok
Unknown route returns standard error response
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

## 8. CI/CD expectations

The API CI workflow should validate at least:

```text
install dependencies
run pytest
build Docker image
```

A failed test or failed Docker build should block the change.

This supports the RetailOps delivery quality goal: every API change should be automatically validated before it is treated as safe to merge or extend.

---

## 9. Security expectations

The API should follow secure-by-default conventions:

- do not expose secrets in responses,
- do not expose stack traces to clients,
- keep error messages safe and minimal,
- validate request inputs,
- avoid leaking infrastructure details,
- prepare future endpoints for authentication and RBAC.

Authentication and RBAC are not implemented in CS-007, but the API conventions should not conflict with future security design.

---

## 10. Observability expectations

The `/health` endpoint is the first observability-related API contract.

It supports:

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

These are not required for CS-007, but the current conventions should allow them to be added later.
