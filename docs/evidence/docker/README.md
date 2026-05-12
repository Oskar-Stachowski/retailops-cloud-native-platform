# Docker Evidence

Last reviewed: 2026-05-12

This folder stores curated Docker and local runtime evidence for reviewer-facing production-readiness claims.

| File | What it proves | Related checklist row | Validation note |
|---|---|---|---|
| `compose-ci-smoke.md` | Backend and frontend images build; the full Compose stack starts; API, frontend, streaming and observability smoke tests pass; cleanup runs. | DOCKER-001, DOCKER-002, DOCKER-005 | Captured from `make compose-ci`. |

## Refresh Command

```bash
make compose-ci
```

This command validates Compose config, builds the backend and frontend images, starts the full local stack, runs smoke checks, runs streaming and observability smoke checks, then tears the stack down.
