# Database recovery evidence

Verified on 2026-09-25 with `make db-recovery-drill` from clean commit
`21e916580f8c1e4604e98d3fb8c249aea94f91c8`.

Environment: local Docker Desktop, Linux ARM64 containers, PostgreSQL 16.13,
committed demo fixture, cached API image build. The isolated project was
`retailops-recovery-5975b53fd5b9`. No normal RetailOps database or volume was
used. Source and restore target were separate databases in the disposable
PostgreSQL container.

The [captured JSON report](2026-09-25-recovery.json) records `passed`, a clean
working tree, matching before/after fingerprints and successful cleanup.
[Runbook and reproducible command](../../runbooks/db-restore.md).

| Check | Result |
|---|---|
| Full contents of all 15 public tables, including migration revision | Identical counts and hashes; 66 rows restored |
| Column types/defaults/nullability, constraints and indexes | Matching schema fingerprint |
| Sequence state inventory | Matches; this schema has no sequences and uses UUID defaults |
| Alert acknowledge → resolve | Resolved decision retained |
| Recommendation accept → resolve | Implemented decision retained |
| Second recommendation reject | Rejected decision, actor and comment retained |
| Workflow actions / audit log before and after restore | 6 / 5 rows, identical contents |
| Replay all five HTTP mutations with original idempotency keys | Original responses returned; no duplicate history |
| HTTP health/readiness and Product 360 | Passed against restored database |
| New comment after restore | Succeeded; exactly one new workflow row and audit row |
| Missing dump / missing checksum / corrupt dump / invalid archive | All four rejected; empty target unchanged |
| Relocated backup/checksum pair | Restored successfully after original path ceased to exist |
| Source database unchanged / temporary resources removed | Passed |

CHECK definitions are reparsed by PostgreSQL in temporary empty tables for
comparison. This accounts for equivalent array-cast syntax after a logical
restore without ignoring constraints or modifying source records. No seed or
migration ran on the restored target before validation.

## Measured durations

| Operation | Seconds |
|---|---:|
| Backup command | 0.338 |
| Restore command | 0.381 |
| Restore plus content and application verification | 3.643 |
| Entire drill, including cached build, setup and cleanup | 23.622 |

The custom-format dump was 61,501 bytes. Its checksum is in the JSON report.
These are measured durations for a small, quiescent synthetic fixture, not
production RTO/RPO, large-volume recovery, point-in-time recovery or application
version rollback evidence. Empty forecast-run and streaming tables were
restored as empty; this run does not demonstrate recovery of populated broker
state or ML runs.

The command is part of the required Docker CI gate. CI uploads only `report.json`
and `commands.log` under the `docker-compose-ci-evidence` artifact. Local dumps,
checksums and expected workflow payloads remain in ignored `ci-cd/reports/db/`.
The tracked report above is from the dated local execution, not a CI run.
