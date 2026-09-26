# Versioned application rollback evidence

Published registry release evidence: [v0.2.1, 2026-09-26](2026-09-26-registry.md),
including verified signatures and a fresh-runner digest-pull rollback. The
remainder of this page preserves the earlier local drill capture.

Verified locally on 2026-09-25 from clean harness commit
`977c776ed7cf80ae2229e1522dba8a44e3827a75` using:

```bash
PLAYWRIGHT_BROWSER_CHANNEL=chrome make release-drill
```

Environment: Docker Desktop, Linux ARM64 API/frontend/PostgreSQL containers,
headless installed Chrome, one disposable database with the committed demo
fixture. The [captured report](2026-09-25-rollback.json) contains exact image IDs,
source commits, migration fingerprints, table hashes and timings.

| Version | Source commit | Role in the drill |
|---|---|---|
| `0.1.0+git.44f7404010b5` | `44f7404010b55eba3d9bacd888d2dc7bb9797180` | Frozen earlier CI-verified baseline; exact images reused for rollback |
| `0.2.0+git.977c776ed7cf` | `977c776ed7cf80ae2229e1522dba8a44e3827a75` | Candidate deployed after the baseline |

These were local candidates, not published Git releases or registry images.
The historical baseline is fixed for this repeatable drill; it is not a default
production rollback recommendation. Each future release must choose and verify
its actual predecessor.

## Results

- Baseline, upgraded and rolled-back stages all passed HTTP health/readiness,
  exact Product 360 decision checks and five idempotent mutation replays.
- All three stages passed browser dashboard counts, Product 360 statuses and
  page reloads. The rollback browser check is scoped to these read journeys;
  the separate seven critical E2E journeys test the current application in CI.
- The original 15 tables / 66 rows were unchanged by deployment and replay.
  A new-version comment added one workflow row and one audit row (68 rows).
  Both survived rollback. A further comment under the older version succeeded
  and produced 70 total rows. No rows were restored from backup or reseeded.
- Both API and frontend containers used exactly the image IDs stored in the
  corresponding manifests; rollback did not rebuild images.
- Stopping the candidate API produced an actual HTTP 502 through Nginx. The
  drill detected it, switched back to both previous images and verified them.
- Changed migration contents at the same head and an unknown live DB revision
  were refused by the migration gate. Five standard-library unit tests also
  cover mismatched image identity/revision and migration fingerprint behavior.
- Both versions had Alembic head `6b0f1c2d3e4a` and identical migration history.
  No Alembic downgrade, database restore or post-upgrade seed was performed.
- The pre-update backup was created. Containers, volume, network and temporary
  application image tags were removed. Existing RetailOps resources were not used.

## Timings and boundaries

| Measurement | Seconds |
|---|---:|
| Update and API/browser/data verification | 26.410 |
| Rollback and API/browser/data verification | 19.255 |
| Whole drill, including builds, setup, failure injection and cleanup | 266.070 |

Rollback timing starts immediately before restoring the previous services,
includes health waits and HTTP/browser/data checks, and excludes the later new
comment and final cleanup. This small synthetic fixture and controlled API
outage do not establish production RTO/RPO, zero downtime, arbitrary schema
reversibility, broker recovery or rollback of every possible faulty image.

[Release policy](../../governance/releases.md) ·
[Executable rollback runbook](../../runbooks/application-rollback.md).

The Docker Required CI gate runs the same drill with Chromium and retains its
report/manifests/log and browser failure traces in `docker-compose-ci-evidence`.
The committed JSON above is the dated local result; it is not a CI capture.

The secret scanner's generic API-key rule initially mistook the two public
Git-based API image tags in this dated JSON for credentials. The exception in
`.gitleaks.toml` is assigned only to that rule, this exact evidence path and
those two literal tag values, using a rule-level allowlist compatible with
Gitleaks 8.24.3 (the CI action's version) and 8.30.1 (the local version).
Both versions passed the report and branch-history scans, while rejecting
both a synthetic GitHub token and a synthetic generic API key inserted into
the same path. No real credential was used in that test.
