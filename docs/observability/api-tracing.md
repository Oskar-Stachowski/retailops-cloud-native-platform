# API OpenTelemetry tracing

## Purpose

RetailOps API supports optional OpenTelemetry HTTP request tracing for FastAPI. Tracing is disabled by default so local development and CI remain lightweight.

## Configuration

| Environment variable | Default | Description |
|---|---|---|
| `RETAILOPS_OTEL_ENABLED` | `false` | Enables FastAPI tracing when set to `true`, `1`, `yes` or `on`. |
| `RETAILOPS_OTEL_SERVICE_NAME` | `retailops-api` | Service name attached to traces. |
| `RETAILOPS_OTEL_EXPORTER` | `console` | `console` for local smoke logs, `otlp` for an OTLP collector. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | unset | OTLP/HTTP collector endpoint used when exporter is `otlp`. |
| `RETAILOPS_OTEL_TRACE_SAMPLE_RATE` | `1.0` | Trace sampling ratio from `0.0` to `1.0`. |
| `RETAILOPS_OTEL_EXCLUDED_URLS` | `/health,/ready,/metrics` | Comma-separated URLs excluded from tracing noise. |

## Local console smoke

```bash
cd services/api
RETAILOPS_OTEL_ENABLED=true \
RETAILOPS_OTEL_EXPORTER=console \
PYTHONPATH=. \
uvicorn app.main:app --reload

curl -H 'X-Correlation-ID: trace-smoke-001' 'http://localhost:8000/products?limit=1&offset=0'
```

Expected evidence: JSON span output in API logs.

## OTLP collector smoke

Run with a collector-backed observability stack and set:

```bash
RETAILOPS_OTEL_ENABLED=true
RETAILOPS_OTEL_EXPORTER=otlp
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318/v1/traces
```

Expected evidence: trace screenshot from Jaeger, Tempo, Grafana or another OTLP-compatible backend.

## Claim boundary

Safe wording after runtime evidence exists:

> Added opt-in OpenTelemetry tracing for FastAPI HTTP requests with local console and OTLP collector export modes.

Do not claim full distributed tracing across frontend, broker, database and background workers until those spans are instrumented and evidenced.
