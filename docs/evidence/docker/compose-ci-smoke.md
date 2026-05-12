# Docker Compose CI Smoke Evidence

Captured: 2026-05-12

## Command

```bash
make compose-ci
```

The first sandboxed attempt could validate Compose config but could not access the local Docker socket. The successful run used the same command with permission to access local Docker.

## Build Evidence

The command built both application images:

```text
Image retailops-api:0.1.0 Built
Image retailops-frontend:0.1.0 Built
```

Local image metadata after the run:

| Image | Image ID | Size |
|---|---|---:|
| `retailops-api:0.1.0` | `sha256:5b1b4f5560ab5d400a33b1c0e9d4bfdd6ec7705d04d217be7bbfe342e7e36b83` | 73182416 bytes |
| `retailops-frontend:0.1.0` | `sha256:7bd56762e5681652c48db59d4809364ba6f2cab5f98c886f006ae6586b322e5c` | 25839238 bytes |

## Compose Startup Evidence

The full local stack started successfully:

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

## Compose Smoke Evidence

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
[streaming-smoke] Checking Prometheus target health (3/30)...
[streaming-smoke] Checking Prometheus target health (4/30)...
[streaming-smoke] Checking Prometheus stream alert rules...
[streaming-smoke] Streaming smoke test passed.
```

## Observability Smoke Evidence

```text
[observability-smoke] API is reachable.
[observability-smoke] Prometheus is reachable.
[observability-smoke] Grafana is reachable.
[observability-smoke] Checking API metrics...
[observability-smoke] Checking Prometheus targets...
[observability-smoke] Checking Prometheus rules...
[observability-smoke] Checking Grafana datasource...
[observability-smoke] Checking Grafana dashboards...
[observability-smoke] Observability smoke test passed. Evidence saved under ci-cd/reports/observability.
```

## Cleanup Evidence

```text
[compose-ci] Cleaning Compose stack...
Container retailops-cloud-native-platform-api-1 Removed
Container retailops-cloud-native-platform-db-1 Removed
Network retailops-cloud-native-platform_default Removed
Volume retailops-cloud-native-platform_postgres_data Removed
Volume retailops-cloud-native-platform_prometheus_data Removed
Volume retailops-cloud-native-platform_grafana_data Removed
Volume retailops-cloud-native-platform_redpanda_data Removed
```
