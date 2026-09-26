# Local scrape availability objective

The initial monitoring objective is **99.9% successful API metric scrapes over
30 days**, per API target, at the configured 15-second interval. It measures the
availability of the `/metrics` path from Prometheus, including the metric
collector's database access. It does not measure successful user requests,
frontend availability, latency percentiles, or a production SLA.

| Signal | Query / interpretation |
|---|---|
| Current reachability | `up{job="retailops-api"}` |
| Incident diagnostic | `retailops:api_scrape_availability:ratio5m` |
| 30-day observed ratio | `retailops:api_scrape_availability:ratio30d` |
| Evidence coverage | `retailops:api_scrape_samples:count30d` |
| Outage alert | `RetailOpsApiMetricsTargetDown`, `up == 0` continuously for 2 minutes |

The recording rules calculate `avg_over_time(up[window])`. Each failed scrape
contributes zero. Missing Prometheus samples are **unknown**, not successful
scrapes. An empty vector is not 100%. Do not call the objective met until there
are 30 days of continuous observation, approximately 172,800 samples per target,
and independent evidence that Prometheus itself stayed operational. Its local
35-day retention allows that observation window but does not provide durable or
highly available monitoring. Target replacement and monitoring gaps require
review before combining periods. A 99.9% objective allows 43.2 minutes of failed
scrapes in a fully observed 30-day window.

`make compose-ci` creates a disposable stack and checks healthy ingestion,
Grafana datasource queries and four provisioned dashboards. It stops only that
stack's API, observes the real alert's inactive → pending → firing transition,
checks that the 5-minute ratio decreases, starts the API and verifies recovery
and resolution. The two-minute threshold is unchanged. The rolling ratio may
remain reduced after recovery until the outage leaves its window.

The report is `ci-cd/reports/observability/incident-drill.json`; source identity,
image IDs and verified resource cleanup are in
`ci-cd/reports/docker/isolated-runtime.json`. A short successful drill validates
the signal and response mechanics; **it does not establish 30-day compliance**.
There is no configured Alertmanager or notification receiver, so firing means
visible in Prometheus, not delivered to an operator. Request SLIs, notification
delivery, centralized logs and end-to-end tracing remain future work.

Rule regression tests include the hold duration, recovery and absent data:

```bash
docker run --rm --entrypoint=/bin/promtool \
  -v "$PWD/observability/prometheus:/work:ro" \
  prom/prometheus:v3.7.3 test rules /work/tests/outage.yml
```

Test format: [Prometheus rule unit testing](https://prometheus.io/docs/prometheus/latest/configuration/unit_testing_rules/).
