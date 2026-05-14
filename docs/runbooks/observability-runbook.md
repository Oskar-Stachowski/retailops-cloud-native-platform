# Observability Runbook

**Project:** Cloud-Native RetailOps Platform
**Workstream:** Observability / Reliability / Local Operations
**Sprint:** Sprint 11 — Observability Foundation
**Commit:** `docs: add observability runbook`

---

## 1. Purpose

This runbook explains how to operate and troubleshoot the local observability
stack for RetailOps.

Use it when:

- Grafana dashboards are missing or stale,
- Prometheus does not show expected metrics,
- `/metrics` returns zeros or missing series,
- alert rules do not appear in Prometheus,
- the API, stream processing or DB instrumentation panels look unhealthy,
- Sprint 11 observability evidence needs to be collected.

Senior DevOps rule:

> First prove the signal path. Then diagnose the service.

Signal path:

```text
FastAPI /metrics -> Prometheus scrape -> Prometheus rules -> Grafana dashboard
```

---

## 2. Local services

| Service | URL | Purpose |
|---|---|---|
| API | `http://localhost:8000` | Application and `/metrics` endpoint. |
| Prometheus | `http://localhost:9090` | Scrapes API metrics and evaluates alert rules. |
| Grafana | `http://localhost:3001` | Dashboards backed by Prometheus. |
| PostgreSQL | `localhost:5432` | Source tables for realtime metrics. |

Grafana local credentials:

```text
admin / retailops
```

---

## 3. Start and stop

Start the observability stack:

```bash
make observability-up
```

Validate the rendered observability profile:

```bash
COMPOSE_PROFILES=observability docker compose config
```

When a separate checklist evidence file is required, validate the thin overlay:

```bash
docker compose -f docker-compose.yml -f docker-compose.observability.yml --profile observability config
```

Stop and remove local state:

```bash
make compose-down
```

Use `compose-down` carefully because it removes local volumes, including
Prometheus, Grafana and PostgreSQL data.

---

## 4. Quick health checks

Check API health:

```bash
curl --silent --show-error http://localhost:8000/health
```

Check API metrics:

```bash
curl --silent --show-error http://localhost:8000/metrics
```

Check Prometheus readiness:

```bash
curl --silent --show-error http://localhost:9090/-/ready
```

Check Prometheus targets:

```bash
curl --silent --show-error \
  "http://localhost:9090/api/v1/targets?state=active"
```

Check Grafana dashboards:

```bash
curl --silent --show-error \
  --user "${GRAFANA_ADMIN_USER}:${GRAFANA_ADMIN_PASSWORD}" \
  http://localhost:3001/api/search
```

Expected dashboard titles:

- `RetailOps Overview`
- `RetailOps API`
- `RetailOps Business Operations`
- `RetailOps Stream Processing`

---

## 5. Expected Prometheus metrics

The API should expose baseline application metrics:

```text
retailops_api_info
retailops_stream_metrics_generated_at_seconds
```

After DB-backed endpoints or readiness checks run, the API should also expose
database instrumentation metrics:

```text
retailops_db_operations_total
retailops_db_operation_duration_seconds_sum
retailops_db_operation_duration_seconds_max
```

When realtime event tables contain data, stream metrics should include:

```text
retailops_stream_latest_event_present
retailops_stream_events_total
retailops_stream_events_by_type_total
retailops_stream_dlq_events_total
retailops_stream_event_freshness_seconds
retailops_stream_processing_latency_seconds_avg
retailops_stream_processing_latency_seconds_max
retailops_stream_consumer_lag_events
retailops_stream_consumer_running
```

Prometheus query examples:

```bash
curl --silent --show-error \
  "http://localhost:9090/api/v1/query?query=up"

curl --silent --show-error \
  "http://localhost:9090/api/v1/query?query=retailops_api_info"

curl --silent --show-error \
  "http://localhost:9090/api/v1/query?query=retailops_db_operations_total"

curl --silent --show-error \
  "http://localhost:9090/api/v1/query?query=retailops_stream_events_total"
```

---

## 6. Dashboard links

Open Grafana:

```text
http://localhost:3001
```

Direct dashboard URLs:

```text
http://localhost:3001/d/retailops-overview/retailops-overview
http://localhost:3001/d/retailops-api/retailops-api
http://localhost:3001/d/retailops-business-operations/retailops-business-operations
http://localhost:3001/d/retailops-stream-processing/retailops-stream-processing
```

If a dashboard is missing, check that Grafana sees the provisioned files:

```bash
COMPOSE_PROFILES=observability docker compose exec -T grafana ls -la /var/lib/grafana-dashboards
```

Then restart only Grafana:

```bash
COMPOSE_PROFILES=observability docker compose restart grafana
```

---

## 7. Alert rules

Prometheus loads alert rule files from:

```text
observability/prometheus/rules/*.yml
```

Current files:

```text
observability/prometheus/rules/api-alerts.yml
observability/prometheus/rules/stream-alerts.yml
```

Check loaded rules:

```bash
curl --silent --show-error http://localhost:9090/api/v1/rules
```

Check active alerts:

```bash
curl --silent --show-error http://localhost:9090/api/v1/alerts
```

If rules are missing:

1. Confirm `docker compose config` shows the rules bind mount.
2. Confirm the file exists under `observability/prometheus/rules`.
3. Restart Prometheus:

```bash
docker compose restart prometheus
```

4. Re-check `/api/v1/rules`.

---

## 8. Common symptoms

| Symptom | Likely cause | First check |
|---|---|---|
| Grafana shows only one dashboard | Grafana provisioned before new JSON file existed. | `COMPOSE_PROFILES=observability docker compose restart grafana` |
| Dashboard panels show `No data` | Prometheus has no matching series. | Query Prometheus directly. |
| Panels show `0` | Signal path works, but source tables have no events or no DB calls. | Check `/metrics`. |
| Prometheus target is down | API not healthy or scrape path unavailable. | `/api/v1/targets?state=active` |
| Alert rules missing | Prometheus has not loaded the rules directory. | `/api/v1/rules` |
| DB metrics missing | No instrumented DB operation has run yet. | Call `/ready` or a DB-backed endpoint. |
| Stream metrics missing | Realtime tables are empty or migrations did not run. | Check `/dashboard/live-operations`. |

---

## 9. Diagnose empty dashboards

Use this order.

1. Check the API directly:

```bash
curl --silent --show-error http://localhost:8000/metrics
```

2. Check Prometheus has scraped the API:

```bash
curl --silent --show-error \
  "http://localhost:9090/api/v1/query?query=up{job=\"retailops-api\"}"
```

3. Query the exact series used by the dashboard:

```bash
curl --silent --show-error \
  "http://localhost:9090/api/v1/query?query=retailops_stream_consumer_lag_events"
```

4. If API has data but Prometheus does not, wait one scrape interval
   (`15s`) and query again.

5. If Prometheus has data but Grafana does not, refresh the dashboard or
   restart Grafana.

---

## 10. Local evidence checklist

Capture these outputs for Sprint 11 evidence:

```bash
mkdir -p ci-cd/reports/observability

curl --silent --show-error http://localhost:8000/metrics \
  > ci-cd/reports/observability/api-metrics.txt

curl --silent --show-error http://localhost:9090/api/v1/targets?state=active \
  > ci-cd/reports/observability/prometheus-targets.json

curl --silent --show-error http://localhost:9090/api/v1/rules \
  > ci-cd/reports/observability/prometheus-rules.json

curl --silent --show-error \
  --user "${GRAFANA_ADMIN_USER}:${GRAFANA_ADMIN_PASSWORD}" \
  http://localhost:3001/api/search \
  > ci-cd/reports/observability/grafana-dashboards.json
```

Review evidence before committing it. Do not commit private hostnames, tokens,
real customer data, or sensitive account identifiers.

---

## 11. Validation commands

Run focused observability tests:

```bash
services/api/.venv/bin/python -m pytest \
  services/api/tests/test_prometheus_configuration.py \
  services/api/tests/test_prometheus_alert_rules.py \
  services/api/tests/test_grafana_provisioning.py \
  services/api/tests/test_metrics_endpoint.py \
  services/api/tests/test_database_instrumentation.py \
  services/api/tests/test_stream_observability.py
```

Run Compose config validation:

```bash
docker compose config
```

Run smoke checks against a running stack:

```bash
make streaming-smoke
```

---

## 12. Escalation notes

Escalate when:

- API `/health` or `/ready` fails after restart,
- Prometheus cannot scrape a healthy API,
- alert rules do not load after validating paths and restarting Prometheus,
- dashboards disappear after provisioning restart,
- DB metrics show sustained errors or high latency,
- stream lag or DLQ alerts remain active after replay/consumer recovery.

Include:

- failing command,
- response body or log snippet,
- dashboard URL,
- relevant Prometheus query,
- recent commits touching `observability/`, `services/api/app/api/metrics.py`
  or DB instrumentation.
