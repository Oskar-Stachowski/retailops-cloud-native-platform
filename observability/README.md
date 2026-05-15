# Observability

This directory will contain observability assets for the RetailOps Platform.

Current status: `Implemented` for local Prometheus metrics, Grafana provisioning, alert rules, and smoke checks. `Target` for centralized logging, distributed tracing, and cloud runtime observability.

Planned MVP / target responsibilities:
- define application and platform metrics,
- store Prometheus configuration,
- store Grafana dashboards,
- define alerting rules,
- document logging and tracing assumptions,
- support operational visibility for APIs, infrastructure, data pipelines, and ML components.

Operational troubleshooting steps live in
[`docs/runbooks/observability-runbook.md`](../docs/runbooks/observability-runbook.md).

Sprint 9 real-time observability should follow
[`docs/real-time-event-contracts.md`](../docs/real-time-event-contracts.md),
especially the metrics for event production, event consumption, failed events,
DLQ count, processing latency, event freshness and consumer lag.

## Sprint 9 Stream Metrics

The API exposes Prometheus text metrics at:

```text
GET /metrics
```

The current stream-processing metrics are derived from:

- `realtime_event_log`,
- `live_metric_observations`,
- `realtime_consumer_state`.

Key metric families:

- `retailops_stream_events_total`
- `retailops_stream_events_by_type_total`
- `retailops_stream_dlq_events_total`
- `retailops_stream_latest_event_present`
- `retailops_stream_event_freshness_seconds`
- `retailops_stream_processing_latency_seconds_avg`
- `retailops_stream_processing_latency_seconds_max`
- `retailops_stream_consumer_lag_events`
- `retailops_stream_consumer_*_events_total`

Local Prometheus scrape configuration lives in
[`observability/prometheus.yml`](prometheus.yml).

Local Grafana provisioning lives under:

```text
observability/grafana/provisioning/
```

The starter dashboard lives at:

```text
observability/grafana/dashboards/retailops-overview.json
```

The API dashboard lives at:

```text
observability/grafana/dashboards/retailops-api.json
```

The business operations dashboard lives at:

```text
observability/grafana/dashboards/retailops-business-operations.json
```

The stream processing dashboard lives at:

```text
observability/grafana/dashboards/retailops-stream-processing.json
```

Alert rules live in:

```text
observability/prometheus/rules/stream-alerts.yml
```

Current alert coverage:

- API `/metrics` scrape target down,
- Prometheus self-scrape target down,
- API service info metric missing,
- database operation metrics missing,
- database operation errors increasing,
- high and critical database operation latency,
- no stream events ingested,
- stale stream events,
- DLQ events increasing,
- consumer failures increasing,
- high and critical consumer lag proxy,
- consumer down or missing,
- high and critical processing latency.

Run the local API and Prometheus/Grafana stack with:

```bash
make observability-up
```

Validate the dedicated observability profile with:

```bash
COMPOSE_PROFILES=observability docker compose config
```

If a checklist requires an explicit observability Compose file, use the thin overlay:

```bash
docker compose -f docker-compose.yml -f docker-compose.observability.yml --profile observability config
```

Run the streaming smoke checks against a running Compose stack with:

```bash
make streaming-smoke
```

Run the observability smoke checks and collect API, Prometheus and Grafana
evidence under `ci-cd/reports/observability` with:

```bash
make observability-smoke
```

When this evidence is refreshed, update the matching metadata row in `docs/evidence/index.md` so the capture date, commit SHA, command, and expected outcome stay visible to reviewers.

Generate a local demo scenario with correlated API traffic, live business
events, duplicate handling and one dead-lettered event with:

```bash
make observability-demo-traffic
```

Then open:

```text
http://localhost:9090
http://localhost:3001
```

Default local Grafana credentials:

```text
admin / retailops
```
