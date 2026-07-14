# Local Runtime Smoke Evidence

Captured: 2026-05-18
Branch: `devops-platform-readiness`
Commit: `5aedb2bdc7d7`

## Commands

```bash
make compose-up
make runtime-smoke-evidence
make compose-down
```

The commands were run with local Docker access because the runtime stack exposes
host ports for API, frontend, Prometheus and Grafana.

## Result

PASS. The same running Compose stack passed:

- API/frontend Compose smoke;
- k6 API smoke baseline;
- Playwright browser smoke against the frontend connected to the API;
- explicit Compose cleanup.

## Compose Smoke

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

## k6 API Smoke Baseline

Script:

```text
tests/performance/k6/api-smoke.js
```

Generated local reports:

```text
ci-cd/reports/performance/api-smoke.txt
ci-cd/reports/performance/api-smoke-summary.json
```

Summary:

| Metric | Result |
|---|---:|
| Checks | 780 / 780 passed |
| Failed checks | 0 |
| Failed HTTP requests | 0.00% |
| HTTP p95 latency | 34.19 ms |
| HTTP p90 latency | 31.16 ms |
| HTTP max latency | 93.68 ms |
| Iterations | 78 |
| VUs | 3 |
| Duration | 30 s |

Validated endpoints:

- `/health`
- `/products`
- `/forecasts`
- `/forecast-runs`
- `/inventory-snapshots`
- `/sales`
- `/inventory-risks`
- `/notifications`
- `/me`
- `/metrics`

Claim boundary:

> This is a small local API smoke baseline with p95 latency evidence. It is not
> a production capacity test or autoscaling proof.

## Playwright Browser Smoke

Spec:

```text
frontend/e2e/retailops-smoke.spec.js
```

Generated local reports:

```text
ci-cd/reports/e2e/playwright-junit.xml
ci-cd/reports/e2e/dashboard-smoke-snapshot.png
```

Summary:

| Metric | Result |
|---|---:|
| Browser project | Chromium |
| Tests | 1 |
| Passed | 1 |
| Failures | 0 |
| Errors | 0 |
| Skipped | 0 |
| Test time | 3.473 s |
| Suite time | 5.563631 s |

Validated browser path:

- API `/health` responds before page checks;
- dashboard loads at `/`;
- business KPI metrics render;
- backend integration status renders;
- dashboard screenshot is captured;
- navigation to `/products` works;
- product catalog and backend product records render.

Claim boundary:

> This is a browser-level smoke test for the primary demo path. It is not a full
> UI regression suite.

## Cleanup

The final cleanup command removed the local stack:

```bash
make compose-down
```

A follow-up `docker compose ps` check returned no running services:

```text
NAME      IMAGE     COMMAND   SERVICE   CREATED   STATUS    PORTS
```
