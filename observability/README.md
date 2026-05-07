# Observability

This directory will contain observability assets for the RetailOps Platform.

Planned MVP / target responsibilities:
- define application and platform metrics,
- store Prometheus configuration,
- store Grafana dashboards,
- define alerting rules,
- document logging and tracing assumptions,
- support operational visibility for APIs, infrastructure, data pipelines, and ML components.

Sprint 9 real-time observability should follow
[`docs/real-time-event-contracts.md`](../docs/real-time-event-contracts.md),
especially the metrics for event production, event consumption, failed events,
DLQ count, processing latency, event freshness and consumer lag.

Implementation will be added in later tasks.
