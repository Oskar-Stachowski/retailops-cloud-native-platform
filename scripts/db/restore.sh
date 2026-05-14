#!/usr/bin/env bash
set -euo pipefail

COMPOSE_CMD="${COMPOSE:-docker compose}"
DB_SERVICE="${DB_SERVICE:-db}"
POSTGRES_USER="${POSTGRES_USER:-retailops}"
POSTGRES_DB="${POSTGRES_DB:-retailops}"
DUMP_MODE="${RETAILOPS_DB_DUMP_MODE:-compose}"
BACKUP_FILE="${1:-${BACKUP_FILE:-}}"

if [[ -z "${BACKUP_FILE}" ]]; then
  echo "ERROR: provide a backup file path as the first argument or set BACKUP_FILE." >&2
  echo "Example: scripts/db/restore.sh ci-cd/reports/db/backups/retailops-retailops-20260514T090000Z.dump" >&2
  exit 1
fi

if [[ ! -s "${BACKUP_FILE}" ]]; then
  echo "ERROR: backup file does not exist or is empty: ${BACKUP_FILE}" >&2
  exit 1
fi

if [[ -f "${BACKUP_FILE}.sha256" ]]; then
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum --check "${BACKUP_FILE}.sha256"
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 --check "${BACKUP_FILE}.sha256"
  else
    echo "ERROR: checksum file exists but neither sha256sum nor shasum is available." >&2
    exit 1
  fi
fi

if [[ "${DUMP_MODE}" == "local" ]]; then
  if [[ -z "${DATABASE_URL:-}" ]]; then
    echo "ERROR: DATABASE_URL is required when RETAILOPS_DB_DUMP_MODE=local." >&2
    exit 1
  fi
  command -v pg_restore >/dev/null 2>&1 || {
    echo "ERROR: pg_restore is not available in PATH." >&2
    exit 1
  }
  pg_restore \
    --clean \
    --if-exists \
    --no-owner \
    --no-privileges \
    --dbname "${DATABASE_URL}" \
    "${BACKUP_FILE}"
else
  ${COMPOSE_CMD} ps "${DB_SERVICE}" >/dev/null
  ${COMPOSE_CMD} exec -T "${DB_SERVICE}" \
    pg_restore \
      --clean \
      --if-exists \
      --no-owner \
      --no-privileges \
      --username "${POSTGRES_USER}" \
      --dbname "${POSTGRES_DB}" \
    < "${BACKUP_FILE}"
fi

echo "Database restore completed from: ${BACKUP_FILE}"
