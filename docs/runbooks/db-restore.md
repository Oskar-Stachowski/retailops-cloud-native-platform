# Database backup and restore runbook

## Purpose

This runbook documents the local RetailOps PostgreSQL backup/restore drill for portfolio readiness evidence. It is designed for the Docker Compose development database and for CI/local proof, not for managed production RDS backups.

## Scope

Covered:

- create a logical PostgreSQL dump from the local Compose database,
- store checksum evidence,
- restore the dump into the local Compose database,
- validate that migrations and seed data still work after restore.

Not covered:

- production RPO/RTO guarantees,
- cross-region backups,
- encrypted object-store retention,
- point-in-time recovery for managed PostgreSQL.

## Prerequisites

From the repository root:

```bash
docker compose up -d db
make docker-build
make compose-up
```

The default Compose database service is `db`. If your local service has a different name, set `DB_SERVICE` before running the scripts.

## Backup

```bash
scripts/db/backup.sh
```

Default output:

```text
ci-cd/reports/db/backups/retailops-retailops-<UTC timestamp>.dump
ci-cd/reports/db/backups/retailops-retailops-<UTC timestamp>.dump.sha256
```

Useful overrides:

```bash
DB_SERVICE=db POSTGRES_USER=retailops POSTGRES_DB=retailops scripts/db/backup.sh
BACKUP_FILE=ci-cd/reports/db/backups/manual-retailops.dump scripts/db/backup.sh
```

For a non-Compose local database with local `pg_dump` installed:

```bash
RETAILOPS_DB_DUMP_MODE=local DATABASE_URL='postgresql://user:password@localhost:5432/retailops' scripts/db/backup.sh
```

## Restore

```bash
scripts/db/restore.sh ci-cd/reports/db/backups/retailops-retailops-<UTC timestamp>.dump
```

The restore script checks the `.sha256` file when it is present.

For a non-Compose local database with local `pg_restore` installed:

```bash
RETAILOPS_DB_DUMP_MODE=local DATABASE_URL='postgresql://user:password@localhost:5432/retailops' scripts/db/restore.sh ci-cd/reports/db/backups/manual-retailops.dump
```

## Validation after restore

Run the database readiness gates:

```bash
make data-generate
make data-contracts
make data-scenario-report
make api-test-db
```

Recommended row-count check:

```bash
docker compose exec -T db psql -U retailops -d retailops -c "\
SELECT 'products' AS table_name, COUNT(*) FROM products
UNION ALL SELECT 'sales', COUNT(*) FROM sales
UNION ALL SELECT 'inventory_snapshots', COUNT(*) FROM inventory_snapshots
UNION ALL SELECT 'forecasts', COUNT(*) FROM forecasts
UNION ALL SELECT 'anomalies', COUNT(*) FROM anomalies
UNION ALL SELECT 'alerts', COUNT(*) FROM alerts
UNION ALL SELECT 'recommendations', COUNT(*) FROM recommendations
UNION ALL SELECT 'workflow_actions', COUNT(*) FROM workflow_actions;"
```

## Evidence to keep

| Evidence | Path |
| --- | --- |
| Backup dump | `ci-cd/reports/db/backups/*.dump` |
| Backup checksum | `ci-cd/reports/db/backups/*.dump.sha256` |
| Data contract report | `ci-cd/reports/data/data-contract-report.json` |
| Scenario coverage report | `ci-cd/reports/data/scenario-coverage-report.json` |
| Human-readable scenario report | `docs/evidence/data/scenario-coverage-report.md` |
| Restore command output | terminal log or CI artifact screenshot |

## Claim boundary

Safe claim after a successful drill:

> RetailOps has a documented local PostgreSQL backup/restore drill with checksum evidence and post-restore validation gates.

Careful claim:

> This is local logical-backup evidence. Do not claim production-grade DR until managed backups, encryption, retention, restore testing, RPO/RTO and runbook ownership are implemented for the target cloud database.
