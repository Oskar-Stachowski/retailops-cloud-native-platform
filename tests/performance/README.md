# RetailOps API performance smoke baseline

This directory contains a small k6 smoke baseline for the Backend/API production-readiness checklist.

## Scope

This is a local smoke baseline, not a production capacity test. It proves that the API can be exercised with repeatable load-test tooling and that a p95 latency report can be captured as evidence.

Covered endpoints:

- `GET /health`
- `GET /products`
- `GET /forecasts`
- `GET /forecast-runs`
- `GET /inventory-snapshots`
- `GET /sales`
- `GET /inventory-risks`
- `GET /notifications`
- `GET /me`
- `GET /metrics`

## Run

```bash
make compose-up
make performance-smoke
```

Optional overrides:

```bash
API_BASE_URL=http://localhost:8000 K6_VUS=5 K6_DURATION=60s make performance-smoke
```

## Evidence

Expected evidence files:

- `ci-cd/reports/performance/api-smoke.txt`
- `ci-cd/reports/performance/api-smoke-summary.json`

The summary JSON is the main machine-readable evidence for p95 latency and failed request rate.

## Claim boundary

Safe CV claim after a passing run: `Added a repeatable k6 API smoke baseline with p95 latency evidence for key read endpoints.`

Do not claim production capacity, autoscaling validation, or full load readiness from this smoke alone.
