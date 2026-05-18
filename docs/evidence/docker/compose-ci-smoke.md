# Docker Compose CI Smoke Evidence

Captured: 2026-05-18
Branch: `devops-platform-readiness`
Commit: `5aedb2bdc7d7`
Command:

```bash
make compose-ci
```

The command was run with local Docker access because the Compose stack depends
on the host Docker socket and host-published ports.

## Result

PASS. `make compose-ci` completed the full local runtime gate and cleaned up the
stack at the end.

Validated stages:

- previous Compose state cleanup;
- default Compose config render;
- profile config render for `dev`, `test`, `observability` and `security`;
- API and frontend Docker image build;
- local stack startup with PostgreSQL, Redpanda, migration job, seed job, API,
  frontend, Prometheus and Grafana;
- API/frontend Compose smoke;
- streaming smoke;
- observability smoke;
- final Compose teardown with volumes and network removed.

## Build Evidence

The command built both application images:

```text
Image retailops-api:0.1.0 Built
Image retailops-frontend:0.1.0 Built
```

Frontend production build inside Docker completed successfully:

```text
vite v8.0.12 building client environment for production...
56 modules transformed.
dist/index.html
dist/assets/index-DYafTXil.css
dist/assets/index-C0iMcHuL.js
```

## Compose Startup Evidence

The full local stack reached the expected healthy/started states:

```text
Container retailops-cloud-native-platform-db-1 Healthy
Container retailops-cloud-native-platform-redpanda-1 Healthy
Container retailops-cloud-native-platform-migrate-1 Exited
Container retailops-cloud-native-platform-seed-1 Exited
Container retailops-cloud-native-platform-api-1 Healthy
Container retailops-cloud-native-platform-frontend-1 Started
Container retailops-cloud-native-platform-prometheus-1 Healthy
Container retailops-cloud-native-platform-grafana-1 Started
```

## API And Frontend Smoke Evidence

```text
[compose-smoke] API is reachable at http://localhost:8000.
[compose-smoke] Checking /health...
[compose-smoke] Checking /ready...
[compose-smoke] Checking /products...
[compose-smoke] Checking /forecasts...
[compose-smoke] Checking /dashboard/summary...
[compose-smoke] Checking /inventory-risks...
[compose-smoke] Frontend is reachable at http://localhost:3000.
[compose-smoke] Checking frontend root...
[compose-smoke] Checking frontend API proxy /api/health...
[compose-smoke] Checking frontend API proxy /api/ready...
[compose-smoke] Compose smoke test passed.
```

## Streaming Smoke Evidence

```text
[streaming-smoke] API is reachable at http://localhost:8000.
[streaming-smoke] Prometheus is reachable at http://localhost:9090.
[streaming-smoke] Checking Redpanda topics (1/30)...
[streaming-smoke] Checking live operations API...
[streaming-smoke] Checking stream metrics endpoint...
[streaming-smoke] Checking Prometheus target health (1/30)...
[streaming-smoke] Checking Prometheus target health (2/30)...
[streaming-smoke] Checking Prometheus stream alert rules...
[streaming-smoke] Streaming smoke test passed.
```

## Observability Smoke Evidence

Grafana returned one transient connection reset while it was still starting, then
became reachable inside the retry window. The smoke gate passed:

```text
[observability-smoke] API is reachable.
[observability-smoke] Prometheus is reachable.
[observability-smoke] Waiting for Grafana (1/30)...
[observability-smoke] Grafana is reachable.
[observability-smoke] Checking API metrics...
[observability-smoke] Checking Prometheus targets...
[observability-smoke] Checking Prometheus rules...
[observability-smoke] Checking Grafana datasource...
[observability-smoke] Checking Grafana dashboards...
[observability-smoke] Observability smoke test passed. Evidence saved under ci-cd/reports/observability.
```

## Cleanup Evidence

`make compose-ci` removed the containers, volumes and network at the end of the
run. A follow-up `docker compose ps` check returned no running services:

```text
NAME      IMAGE     COMMAND   SERVICE   CREATED   STATUS    PORTS
```

Safe claim:

> The full local Docker Compose runtime gate builds the images, starts the stack,
> validates API/frontend, streaming and observability smoke checks, and tears the
> environment down cleanly.
