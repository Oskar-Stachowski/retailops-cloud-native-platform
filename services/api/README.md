# RetailOps API Service

Minimal FastAPI service for the RetailOps platform.  
Provides a basic `/health` endpoint used for testing, monitoring, Docker health checks, and CI/CD validation.

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
- the initial domain models validate core RetailOps data rules

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
