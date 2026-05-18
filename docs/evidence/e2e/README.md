# E2E Evidence Capture

Last reviewed: 2026-05-18

This folder documents local and CI-safe browser/API evidence capture for the
RetailOps application. The automation proves that the React frontend can load
real backend-backed pages and that representative FastAPI business endpoints
return usable responses.

## Prerequisites

- Frontend dependencies installed with `cd frontend && npm ci`.
- Playwright browsers installed for CI, or a compatible local browser available
  through `PLAYWRIGHT_BROWSER_CHANNEL`.
- The local RetailOps stack already running, for example:

```bash
make compose-up
```

Default runtime URLs:

- `FRONTEND_BASE_URL=http://localhost:3000`
- `API_BASE_URL=http://localhost:8000`

Both can be overridden when the stack is exposed on different ports.

## Command

```bash
make evidence-frontend-api
```

The target runs `frontend/e2e/frontend-api-evidence.spec.js` through Playwright.
It is evidence automation, not strict visual regression testing. It checks that
pages render, waits for API-connected content to settle, captures full-page
screenshots, and records API responses without pixel-perfect screenshot
assertions.

By default the target also runs `make observability-demo-traffic` before
Playwright so the Live Operations page contains fresh stream/business activity
instead of an empty zero-state. This uses the repository's existing
`scripts/dev/observability_demo_traffic.sh` and
`services/api/scripts/generate_observability_demo_events.py` helpers. If a run
must capture the current stack state without generating traffic, set:

```bash
EVIDENCE_GENERATE_TRAFFIC=0 EXPECT_LIVE_OPERATIONS_TRAFFIC=0 make evidence-frontend-api
```

## Output Paths

Screenshots are written to:

```text
docs/evidence/frontend-api/
```

API smoke output is written to:

```text
ci-cd/reports/e2e/frontend-api-smoke.json
ci-cd/reports/e2e/frontend-api-smoke.txt
ci-cd/reports/e2e/playwright-junit.xml
```

The `ci-cd/reports/e2e/` files are generated reports and may stay ignored unless
a sanitized snapshot is intentionally promoted. The screenshots under
`docs/evidence/frontend-api/` are recruiter-facing proof artifacts when captured
from a clean local or CI run.

## What This Proves

- The frontend can load the Dashboard, Live Operations, Products, Product 360,
  Forecasts, Anomalies, Recommendations, Action Queue, Admin, and Profile pages.
- The browser flow is connected to the backend instead of static mock-only data.
- Live Operations has fresh generated stream/business traffic when the default
  traffic generation step is enabled.
- `/health` and `/ready` respond successfully.
- Representative business endpoints used by the frontend respond successfully:
  dashboard, live operations, product catalog, Product 360, forecasts, inventory
  risk, analytics, sales, inventory snapshots, identity, notifications, and
  permissions.

## Claim Boundary

This evidence does not prove production scale, accessibility completeness,
cross-browser compatibility, or pixel-perfect UI stability. It is a practical
portfolio/runtime proof that the local or CI stack is connected and usable.
