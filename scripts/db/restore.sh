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

if [[ ! -s "${BACKUP_FILE}.sha256" ]]; then
  echo "ERROR: a non-empty backup checksum file is required." >&2
  exit 1
fi
# Verify the supplied dump, even when the pair was moved from its original path.
read -r expected_checksum _ < "${BACKUP_FILE}.sha256"
if [[ ! "${expected_checksum}" =~ ^[[:xdigit:]]{64}$ ]]; then
  echo "ERROR: invalid SHA-256 checksum." >&2
  exit 1
fi
if command -v sha256sum >/dev/null 2>&1; then
  actual_checksum=$(sha256sum "${BACKUP_FILE}")
elif command -v shasum >/dev/null 2>&1; then
  actual_checksum=$(shasum -a 256 "${BACKUP_FILE}")
else
  echo "ERROR: neither sha256sum nor shasum is available." >&2
  exit 1
fi
if [[ "${actual_checksum%% *}" != "${expected_checksum}" ]]; then
  echo "ERROR: backup checksum mismatch." >&2
  exit 1
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
    --exit-on-error \
    --single-transaction \
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
      --exit-on-error \
      --single-transaction \
      --clean \
      --if-exists \
      --no-owner \
      --no-privileges \
      --username "${POSTGRES_USER}" \
      --dbname "${POSTGRES_DB}" \
    < "${BACKUP_FILE}"
fi

echo "Database restore completed from: ${BACKUP_FILE}"
