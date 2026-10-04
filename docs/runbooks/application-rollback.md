# Application update and rollback runbook

## Execute the isolated drill

```bash
make release-drill
```

Requirements: Docker, Python 3.11+, full Git history, Node and the locked frontend
Playwright dependencies (`cd frontend && npm ci && npx playwright install chromium`).
On a workstation with installed Chrome, use
`PLAYWRIGHT_BROWSER_CHANNEL=chrome make release-drill`. CI installs Chromium.

Default predecessor: `44f7404010b55eba3d9bacd888d2dc7bb9797180`, the dependency/image
refresh baseline documented in the [September CI evidence](../evidence/github-actions/2026-09-25-validation.md).
The candidate is committed `HEAD`; both refs must exist locally, differ, and the
predecessor must be an ancestor of the candidate. To choose a reviewed pair:

```bash
python3 scripts/release/drill.py --previous-ref <previous-SHA> --candidate-ref <candidate-SHA>
```

The drill creates its own Compose project, volume and database. It ignores
normal `.env`/Compose settings and exposes only an ephemeral frontend port on
`127.0.0.1`. It builds immutable API/frontend identities from each Git revision,
then performs this sequence:

1. Migrate and seed only the new disposable source database. Use the older API
   for an identical history; for the fingerprinted AI 10 expansion, migrate
   once with the candidate image before either application version writes.
   Seed mechanics forecast/inbox, partition checkpoint and transport receipt
   rows as well as the legacy demo data.
2. Record an alert acknowledgement/resolution, recommendation acceptance/
   completion and a second recommendation rejection through actual HTTP APIs.
3. Start the older API/frontend images. Verify HTTP, browser dashboard/Product
   360/reload, all table fingerprints, schema and five idempotent requests.
4. Create a pre-update database backup with its checksum.
5. Check migration compatibility and prove that a rewritten migration history
   or unknown database revision blocks application-only rollback.
6. Deploy the candidate by exact image IDs, run the same checks, and write a new
   workflow comment under the new version.
7. Stop the candidate API deliberately. Detect HTTP 502 through Nginx, recheck
   migration compatibility and replace both services with the original images.
8. Verify container image IDs, HTTP and browser behavior, preserved data including
   the new-version write, and idempotent history. Write another comment under
   the rolled-back version to prove continued operation.
9. Remove only this project's containers, volume, network and temporary image
   tags. Keep JSON evidence and logs in ignored local reports.

There is no seed, database restore or Alembic downgrade during rollback. This
proves retention of writes made after the backup. The injected outage represents
an API process failure after a healthy update; this is not a universal production
deployment controller or an arbitrary broken-image test.

## Migration decision

| Situation | Action |
|---|---|
| Identical Alembic head **and complete migration-file fingerprint**, live DB at that head | Application-only rollback is eligible; still verify the running older version and data. |
| Exact parent/expanded fingerprints from `scripts/release/additive-rollback.json`, live DB at one of those two verified heads | Exercise the explicit additive plan on a disposable database, retaining the expanded schema and all seeded ML/transport rows while testing both image versions. |
| Same head but changed migration contents | Block automatic rollback and review the inconsistency. |
| Other new, missing, branched or unknown migration history/revision | Block application-only rollback; prepare an explicit compatibility/forward-fix plan. |
| Destructive schema change or incompatible new data semantics | Stop writes; prefer a reviewed forward fix, or restore a verified backup into a separate database and reconcile/replay later writes before cutover. |

Never run `alembic downgrade` blindly to make the version number match. A
successful application rollback with unchanged schema is not proof that a future
schema change is reversible. The existing [database recovery drill](db-restore.md)
is the separate foundation for backup-based recovery.

The AI 10 plan permits only `6b0f1c2d3e4a` to `a10f0c7e0300` with their exact
complete migration-file fingerprints. The two additive migrations add only
`ai_forecast_results`, `ai_intelligence_inbox`, `ai_intelligence_partitions` and
`ai_intelligence_transport`; existing migrations and tables remain unchanged.
The plan also pins both new migration files individually. Unit guards reject a rewritten parent, changed expansion,
different new head or unknown database revision. Compose and Kubernetes drills
verify the entire expanded schema and all table fingerprints, including a seeded
ML payload/inbox and checkpoint/transport receipt, through restart, update and application rollback. No table
is excluded to make that comparison pass. Kubernetes retains its existing
exception for operational consumer-state counters.

## Evidence and timings

Each run writes `previous-manifest.json`, `candidate-manifest.json`, `report.json`
and `commands.log` under `ci-cd/reports/releases/retailops-release-<id>/`.
Browser failure traces/screenshots are retained by stage. Dumps and expected
workflow payloads are not uploaded by CI.

The report distinguishes update+verification and rollback+verification from
whole-run time, which also includes builds and setup. Measurements use a small,
quiescent synthetic fixture and are not production RTO/RPO guarantees.
The required Docker gate runs the same command and uploads its manifests,
report, log and any browser failure evidence. [Dated results](../evidence/releases/README.md).
