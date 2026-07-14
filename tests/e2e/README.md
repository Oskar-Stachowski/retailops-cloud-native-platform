# RetailOps browser smoke baseline

This directory documents the browser-level smoke responsibility for the local
runtime stack. The executable Playwright spec lives in `frontend/e2e/` because
it uses the frontend package and browser tooling.

## Responsibility split

- k6 owns API performance smoke evidence: endpoint reachability, failed request
  rate, and p95 latency under a small repeatable load.
- Playwright owns browser smoke evidence: the built frontend loads through the
  Compose nginx container, calls the backend through `/api`, renders business
  dashboard evidence, and navigates to a data-backed page.

This is not a full regression suite. It is a recruiter/video-ready runtime
evidence check that proves the most important local demo path works end to end.

## Run

From the repository root:

```bash
make compose-up
make runtime-smoke-evidence
make compose-down
```

To run only the browser layer against an already running stack:

```bash
make browser-smoke
```

Optional overrides:

```bash
FRONTEND_BASE_URL=http://localhost:3000 API_BASE_URL=http://localhost:8000 make browser-smoke
```

`make browser-smoke` defaults to the locally installed Google Chrome channel.
Set `PLAYWRIGHT_BROWSER_CHANNEL=` when using the Playwright-managed Chromium
binary in CI or on a machine where `npx playwright install chromium` has already
been run.

## Evidence

Expected local evidence files:

- `ci-cd/reports/e2e/playwright-junit.xml`
- `ci-cd/reports/e2e/dashboard-smoke-snapshot.png`
- `ci-cd/reports/e2e/playwright-artifacts/` on failure

The screenshot is intentionally local/volatile evidence. Commit curated
snapshots only when they are reviewed and useful for portfolio documentation.
