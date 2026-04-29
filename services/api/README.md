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
http://localhost:8000/docs
```

---

## Tests

Run API tests:

```bash
pytest
```

The test suite currently verifies that the `/health` endpoint returns HTTP `200` and a valid health status.

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
