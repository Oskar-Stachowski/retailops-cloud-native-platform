# Database backup and restore runbook

## Repeatable isolated drill

From the repository root, with Docker Compose and Python 3.11+ available:

```bash
make db-recovery-drill
```

The command builds the current API image and creates a uniquely named
`retailops-recovery-*` Compose project. Its PostgreSQL container has a private
volume and no published host ports. It ignores the normal Compose project,
`.env`, database credentials and existing application volumes. Only resources
created for this drill are removed at the end, including on a test failure.

The source is the committed **demo** fixture. The drill:

1. Runs actual Alembic migrations and seeds only the disposable source database.
2. Uses HTTP workflow endpoints to acknowledge/resolve an alert, accept/resolve
   one recommendation and reject another with a comment and actor identity.
3. Captures counts and hashes of every public table, plus schema and sequence
   metadata, then creates a custom-format PostgreSQL dump and SHA-256 checksum.
4. Moves the backup/checksum pair and creates an empty `restored` database.
5. Verifies that missing dump, missing checksum, corrupt dump and invalid archive
   all fail without changing the target.
6. Restores the relocated dump in one transaction. **No migration or seed runs
   on the restored database before comparison.**
7. Compares every table's complete contents, schema and sequences. Checks HTTP
   health/readiness, Product 360 decisions, idempotent replay of all five actions
   without additional audit entries, and a new workflow write after recovery.
8. Confirms the source is unchanged and removes its own containers, network,
   volume and API image.

A failing check or cleanup returns a nonzero exit code. The Docker Required CI
job runs the same command and uploads the report and command log. Dump files
and raw decision payloads stay in ignored local reports, outside CI artifacts.

## Reports and timing

Each run writes to a new directory:

```text
ci-cd/reports/db/recovery/retailops-recovery-<id>/report.json
ci-cd/reports/db/recovery/retailops-recovery-<id>/commands.log
```

The JSON report records the commit, whether the working tree was dirty,
PostgreSQL version, backup size/hash, table counts/hashes, test outcomes and
cleanup. It measures backup time, restore-command time, restore plus application
verification, and total drill time including build/setup/cleanup. The stopwatch
for restore starts after the empty target and backup are available.

The demonstration uses a small synthetic fixture and a quiescent source.
These timings are **not production RTO/RPO guarantees**, nor a test of managed
RDS backups, point-in-time recovery, encryption, remote retention or large data
volumes. See [dated recovery evidence](../evidence/db/README.md).

## Manual backup of an explicitly selected database

The helpers can also operate on a selected running Compose database. Unlike
the drill, these commands use your supplied/default connection settings.

```bash
make db-backup
```

The default output directory is `ci-cd/reports/db/backups`. Make forwards its
PostgreSQL settings and Compose command to the backup helper. For direct use,
set the user and database to match your stack:

```bash
POSTGRES_USER=retailops POSTGRES_DB=retailops scripts/db/backup.sh
```

For a non-Compose database with local PostgreSQL client tools installed:

```bash
RETAILOPS_DB_DUMP_MODE=local DATABASE_URL='postgresql://user:password@localhost:5432/retailops' scripts/db/backup.sh
```

Keep the dump and adjacent `<dump>.sha256` together. The checksum detects
accidental corruption; it does not authenticate the backup's origin.

## Manual restore

**Restore replaces objects in the selected target database.** Use a separate,
empty database for validation and verify the target settings before running it.
The automated drill above does this isolation for you.

```bash
make db-restore DB_BACKUP_FILE=path/to/backup.dump POSTGRES_DB=restored
```

The adjacent checksum file is required. Verification checks the bytes of the
supplied dump, including after relocation, before connecting to the database.
Missing/invalid checksums or mismatching bytes stop the operation. PostgreSQL
restore uses `--exit-on-error --single-transaction` so a restore error aborts
the transaction instead of leaving partially restored objects.

For local PostgreSQL client tools:

```bash
RETAILOPS_DB_DUMP_MODE=local DATABASE_URL='postgresql://user:password@localhost:5432/restored' scripts/db/restore.sh path/to/backup.dump
```

Validate stored rows, decisions, audit history and application access **before**
regenerating or seeding any data. A seed can replace lost decisions and conceal
an incomplete restore. Application version rollback and migration compatibility
are separate from this database recovery drill.
