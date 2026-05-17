#!/usr/bin/env bash
set -euo pipefail

COMPOSE_CMD="${COMPOSE:-docker compose}"
DB_SERVICE="${DB_SERVICE:-db}"
POSTGRES_USER="${POSTGRES_USER:-retailops}"
POSTGRES_DB="${POSTGRES_DB:-retailops}"
BACKUP_DIR="${BACKUP_DIR:-ci-cd/reports/db/backups}"
BACKUP_FILE="${BACKUP_FILE:-${BACKUP_DIR}/retailops-${POSTGRES_DB}-$(date -u +%Y%m%dT%H%M%SZ).dump}"
DUMP_MODE="${RETAILOPS_DB_DUMP_MODE:-compose}"

mkdir -p "$(dirname "${BACKUP_FILE}")"

if [[ "${DUMP_MODE}" == "local" ]]; then
  if [[ -z "${DATABASE_URL:-}" ]]; then
    echo "ERROR: DATABASE_URL is required when RETAILOPS_DB_DUMP_MODE=local." >&2
    exit 1
  fi
  command -v pg_dump >/dev/null 2>&1 || {
    echo "ERROR: pg_dump is not available in PATH." >&2
    exit 1
  }
  pg_dump \
    --format=custom \
    --no-owner \
    --no-privileges \
    --dbname "${DATABASE_URL}" \
    --file "${BACKUP_FILE}"
else
  ${COMPOSE_CMD} ps "${DB_SERVICE}" >/dev/null
  ${COMPOSE_CMD} exec -T "${DB_SERVICE}" \
    pg_dump \
      --format=custom \
      --no-owner \
      --no-privileges \
      --username "${POSTGRES_USER}" \
      --dbname "${POSTGRES_DB}" \
    > "${BACKUP_FILE}"
fi

if [[ ! -s "${BACKUP_FILE}" ]]; then
  echo "ERROR: backup file is empty: ${BACKUP_FILE}" >&2
  exit 1
fi

if command -v sha256sum >/dev/null 2>&1; then
  sha256sum "${BACKUP_FILE}" > "${BACKUP_FILE}.sha256"
elif command -v shasum >/dev/null 2>&1; then
  shasum -a 256 "${BACKUP_FILE}" > "${BACKUP_FILE}.sha256"
else
  echo "ERROR: neither sha256sum nor shasum is available in PATH." >&2
  exit 1
fi

echo "Database backup created: ${BACKUP_FILE}"
echo "Checksum created: ${BACKUP_FILE}.sha256"
