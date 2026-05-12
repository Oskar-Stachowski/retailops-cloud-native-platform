# RetailOps API Service

FastAPI backend for the RetailOps platform.

The service exposes health and readiness checks, PostgreSQL-backed retail
resources, dashboard read models, mock Sprint 7 identity and notifications, and
Sprint 9 live operations metrics derived from persisted real-time event
processing state.

---

## Local run

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the API locally:

```bash
uvicorn app.main:app --reload
```

Open:

```text
http://localhost:8000/health
http://localhost:8000/ready
http://localhost:8000/dashboard/live-operations
http://localhost:8000/metrics
http://localhost:8000/docs
```

---

## Tests

Run API tests:

```bash
pytest
```

The test suite currently verifies:

- `/health` returns HTTP `200` and a valid health status
- `/ready` returns HTTP `200` when the database is available
- `/ready` returns HTTP `503` when the database is unavailable
- controlled API errors follow the standard error response pattern
- core resource contracts for products, forecasts, inventory snapshots, sales
  and stock risk
- dashboard summary, operational visibility, work item and live operations
  contracts
- Product 360 aggregation
- mock identity, permissions and notifications
- real-time consumer, persisted metrics and Prometheus metric rendering
- domain models and database schema expectations

## Current API Surface

Main public endpoints:

```text
GET /health
GET /ready
GET /metrics

GET /dashboard/summary
GET /dashboard/operational-visibility
GET /dashboard/sales-trend
GET /dashboard/alerts
GET /dashboard/recommendations
GET /dashboard/open-work-items
GET /dashboard/stock-risk-summary
GET /dashboard/live-operations

GET /products
GET /products/{product_id}
GET /products/{product_id}/360
GET /forecasts
GET /forecasts/{forecast_id}
GET /inventory-snapshots
GET /inventory-snapshots/{inventory_snapshot_id}
GET /sales
GET /sales/{sale_id}
GET /inventory-risks

GET /users/demo
GET /me
GET /me/permissions
GET /notifications
POST /notifications/{notification_id}/read
```

Detailed conventions are documented in
[`../../docs/api.md`](../../docs/api.md).

---

## Docker

Build the API image:

```bash
docker build -t retailops-api:0.1.0 .
```

Run the container:

```bash
docker run --rm -p 8000:8000 --name retailops-api retailops-api:0.1.0
```

Check the endpoint:

```bash
curl http://localhost:8000/health
```

---

## Docker Compose

Start the service:

```bash
docker compose up --build
```

Stop the service:

```bash
docker compose down
```

---

## PostgreSQL local checks

Start only the PostgreSQL service:

```bash
docker compose up -d db
```

Check if PostgreSQL is ready:
```bash
docker compose exec db pg_isready -U retailops -d retailops
```

Expected result:
```bash
/var/run/postgresql:5432 - accepting connections
```

Verify the PostgreSQL version:
```bash
docker compose exec db psql -U retailops -d retailops -c "select version();"
```

The local API uses PostgreSQL through DATABASE_URL.

When the API runs inside Docker Compose, the database host is db.

When the API runs directly on your machine, the database host should be localhost.

---

## Health endpoint

```text
GET /health
```

Example response:

```json
{
  "status": "ok",
  "service": "retailops-api",
  "environment": "local"
}
```

---

## Readiness endpoint

```text
GET /ready
```

The readiness endpoint checks whether the API is ready to handle requests that depend on PostgreSQL.

When PostgreSQL is available, the endpoint returns:

```text
HTTP/1.1 200 OK
```

Example response:

```text
{
  "status": "ok",
  "service": "retailops-api",
  "environment": "local",
  "database": "ok"
}
```

When PostgreSQL is unavailable, the endpoint returns:

```text
HTTP/1.1 503 Service Unavailable
```

Example response:

```text
{
  "error": {
    "code": "database_unavailable",
    "message": "Database is not available."
  }
}
```

This endpoint is intended for future Kubernetes readiness probes and deployment safety checks.

---

## Sprint 9 live operations

```text
GET /dashboard/live-operations
GET /metrics
```

Sprint 9 persists real-time event processing output in PostgreSQL:

- `realtime_event_log`
- `live_metric_observations`
- `realtime_consumer_state`

`/dashboard/live-operations` returns the dashboard read model for recent live
sales, inventory, alerts, stream freshness, recent events and consumer state.

`/metrics` renders Prometheus text exposition for stream-processing health.
Local Prometheus and alert rules are documented in
[`../../observability/README.md`](../../observability/README.md).

The API contains a broker-agnostic event processor and a long-running
Redpanda/Kafka runner in `scripts/run_realtime_consumer.py`. The runner polls
configured topics, decodes JSON event envelopes, records live metrics and
commits offsets after each handled message.

---

## Domain Model

The API contains the first MVP domain model for RetailOps in:

`app/domain/models.py`

The model defines the core retail, analytical and operational workflow entities used by the MVP API layer.

---

## CI/CD

GitHub Actions pipeline validates this service by:

- running `pytest`
- building the Docker image

The pipeline is triggered on push and pull request changes affecting the API service.
