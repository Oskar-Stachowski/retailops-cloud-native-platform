# E2E Evidence Capture

Last reviewed: 2026-09-25

This folder documents local and CI-safe browser/API evidence capture for the
RetailOps application. The automation proves that the React frontend can load
real backend-backed pages and that representative FastAPI business endpoints
return usable responses.

## Critical browser gate

`npm run e2e` runs the `chromium` project: seven behavioral journeys against
real frontend, API and PostgreSQL data. Docker Compose CI installs Chromium,
starts a fresh demo-seeded stack and runs these checks before its normal
cleanup. A browser failure propagates to `required-result`. There are no test
retries, skipped critical cases or happy-path API mocks; one worker avoids
racing stateful decisions.

| Journey | Assertions |
|---|---|
| Dashboard | Product count agrees with the API; operational sections load. |
| Catalog and Product 360 | Search, category filter, empty results, reset, navigation and direct reload preserve product identity. |
| Alert workflow in Product 360 | Acknowledge, reload, resolve, persisted status and one audit row per action. |
| Recommendation in Action Queue | Accept, reload, still actionable, resolve to implemented and persist after removal from the queue. |
| Rejection | Missing comment blocks POST; valid comment and rejected status persist. |
| Read-only demo role | User selection survives reload; UI buttons are disabled, direct POST returns 403 and stored status is unchanged. |
| API failure and retry | A controlled 503 shows an error; Retry recovers actual backend catalog rows. |

Run only against disposable demo data: the workflow cases change real records.
They require `E2E_ALLOW_MUTATIONS=1` and fail setup if it is absent. On a fresh
isolated local Compose project, install browsers and run:

```bash
cd frontend && npx playwright install chromium && cd ..
COMPOSE_PROJECT_NAME=retailops-e2e E2E_ALLOW_MUTATIONS=1 \
  PLAYWRIGHT_BROWSER_CHANNEL= make compose-ci COMPOSE_BROWSER_TESTS=1
```

`make compose-ci` creates the demo data and removes that project's volumes at
completion. Re-run it for a clean seed; do not point the workflow suite at a
shared or valuable dataset. Existing `make compose-ci` calls without the
browser opt-in retain their HTTP/streaming/observability checks.

JUnit output and failure screenshots/traces live in `ci-cd/reports/e2e/` and
are uploaded with `docker-compose-ci-evidence`, including on failure. CI does
not overwrite the tracked portfolio screenshots.

The `/dashboard/alerts` feed currently exposes anomaly signals; real alert
workflow actions are exercised in Product 360. The suite verifies the demo
permission boundary, not production authentication. Wider cross-browser,
accessibility and performance checks remain separate work.

## Screenshot capture prerequisites

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

The target runs `frontend/e2e/frontend-api-evidence.spec.js` in the opt-in
`evidence-chromium` Playwright project (three-minute capture timeout).
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
