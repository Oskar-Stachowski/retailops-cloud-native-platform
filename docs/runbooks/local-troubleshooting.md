# Local Runtime Troubleshooting Runbook

**Project:** RetailOps — Cloud-Native AI Platform
**Scope:** Docker Compose, local runtime reproducibility, profile validation and smoke evidence

---

## 1. Purpose

Use this runbook when the local Docker runtime does not start, a reviewer asks
how to reproduce the demo, or Docker evidence has to be refreshed for the
production-readiness checklist.

The local runtime is intentionally not a production deployment. It is a
reviewer-friendly stack for API, frontend, PostgreSQL, Redpanda, Prometheus and
Grafana validation.

---

## 2. Profiles

| Profile | Purpose | Typical command |
|---|---|---|
| `dev` | API, frontend, DB, seed data and broker for local product demo. | `COMPOSE_PROFILES=dev docker compose up --build -d` |
| `observability` | API, DB, Prometheus, Grafana and broker signals for metrics evidence. | `make observability-up` |
| `test` | DB/API-compatible Compose rendering for DB-backed checks and CI validation. | `COMPOSE_PROFILES=test docker compose config` |
| `security` | Containerized security tooling entry point for local scan experiments. | `COMPOSE_PROFILES=security docker compose config` |

The default Makefile profile is `dev`, while the full local reviewer stack uses
`dev,observability` so the existing smoke tests can validate frontend, API,
streaming, Prometheus and Grafana in one run.

---

## 3. Golden path

From the repository root:

```bash
cp .env.example .env
make compose-profile-config
make compose-up
make compose-smoke
make streaming-smoke
make observability-smoke
make docker-runtime-evidence
```

Expected evidence outputs:

```text
ci-cd/reports/docker-compose-ps.txt
ci-cd/reports/docker-compose-logs.txt
ci-cd/reports/docker/compose-profile-dev.yml
ci-cd/reports/docker/compose-profile-test.yml
ci-cd/reports/docker/compose-profile-observability.yml
ci-cd/reports/docker/compose-profile-security.yml
ci-cd/reports/docker/image-users.txt
ci-cd/reports/observability/api-metrics.txt
ci-cd/reports/observability/prometheus-targets.json
ci-cd/reports/observability/grafana-dashboards.json
```

Cleanup:

```bash
make compose-down
```

`make compose-down` removes local volumes. Use it when you want a clean,
reproducible run.

---

## 4. Port matrix

| Service | Default host port | Health check |
|---|---:|---|
| Frontend | `3000` | `curl http://localhost:3000/` |
| API | `8000` | `curl http://localhost:8000/ready` |
| PostgreSQL | `5432` | `docker compose exec db pg_isready -U retailops -d retailops` |
| Redpanda Kafka | `19092` | `docker compose exec redpanda rpk cluster health` |
| Redpanda Admin | `19644` | `curl http://localhost:19644/v1/status/ready` |
| Prometheus | `9090` | `curl http://localhost:9090/-/ready` |
| Grafana | `3001` | `curl http://localhost:3001/api/health` |

If a port is busy, override it in `.env`, for example:

```bash
API_PORT=8010
FRONTEND_PORT=3010
POSTGRES_PORT=55432
PROMETHEUS_PORT=9091
GRAFANA_PORT=3002
```

---

## 5. Common failures

### Port already allocated

Symptom:

```text
Bind for 0.0.0.0:5432 failed: port is already allocated
```

Fix:

```bash
lsof -i :5432
POSTGRES_PORT=55432 make compose-up
```

### API does not become ready

Check DB and migration/seed jobs:

```bash
docker compose ps
docker compose logs --no-color db migrate seed api
curl --silent --show-error http://localhost:8000/ready
```

If local state is corrupted, reset volumes:

```bash
make compose-down
make compose-up
```

### Frontend cannot reach API

Check the Nginx proxy path:

```bash
curl --silent --show-error http://localhost:3000/api/health
curl --silent --show-error http://localhost:3000/api/ready
```

Then inspect frontend logs:

```bash
docker compose logs --no-color frontend
```

### Prometheus target is down

Check that the observability profile is active and the API metrics endpoint is
reachable from the host:

```bash
COMPOSE_PROFILES=observability docker compose config
curl --silent --show-error http://localhost:8000/metrics
curl --silent --show-error "http://localhost:9090/api/v1/targets?state=active"
```

### Grafana dashboard is missing

Check provisioning files and restart Grafana:

```bash
docker compose exec -T grafana ls -la /var/lib/grafana-dashboards
docker compose restart grafana
make observability-smoke
```

---

## 6. Non-root runtime evidence

Build and inspect the images used by Compose:

```bash
make docker-runtime-evidence
cat ci-cd/reports/docker/image-users.txt
```

Expected result:

```text
retailops-api:0.1.0 user=appuser expected=appuser
retailops-frontend:0.1.0 user=101:101 expected=101:101
```

This supports the CV-safe claim that the application containers run as non-root
where practical. Database, broker, Prometheus and Grafana use vendor images and
are documented as local-only dependencies.
