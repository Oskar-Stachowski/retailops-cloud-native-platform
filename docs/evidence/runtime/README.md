# Runtime Smoke Evidence

Last reviewed: 2026-05-18

This folder stores curated evidence for the local runtime smoke path that goes
beyond the basic Compose CI gate.

| File | What it proves | Related area | Validation note |
|---|---|---|---|
| `local-runtime-smoke.md` | Running Compose stack passed API/frontend smoke, k6 API performance smoke and Playwright browser smoke. | Docker, API, frontend, testing | Captured from `make compose-up`, `make runtime-smoke-evidence`, `make compose-down`. |

## Refresh Command

```bash
make compose-up
make runtime-smoke-evidence
make compose-down
```

The raw generated reports are local/volatile by default:

- `ci-cd/reports/performance/api-smoke.txt`
- `ci-cd/reports/performance/api-smoke-summary.json`
- `ci-cd/reports/e2e/playwright-junit.xml`
- `ci-cd/reports/e2e/dashboard-smoke-snapshot.png`

Promote only curated summaries or screenshots when they are useful for reviewer
evidence.
