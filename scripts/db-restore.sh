#!/usr/bin/env bash
# bash scripts/db-restore.sh ./backups/erp-YYYY-MM-DD-HHMMSS.dump
set -euo pipefail

SERVICE_NAME="${SERVICE_NAME:-db}"
DB_USER="${DB_USER:-postgres}"
DB_NAME="${DB_NAME:-erp}"
FORCE="${FORCE:-false}"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <backup-file.dump>"
  echo "Example: $0 ./db_backups/erp-2026-03-27-120000.dump"
  exit 1
fi

BACKUP_FILE="$1"

if [[ ! -f "${BACKUP_FILE}" ]]; then
  echo "[restore] backup file not found: ${BACKUP_FILE}"
  exit 1
fi

if [[ "${FORCE}" != "true" ]]; then
  echo "[restore] WARNING: this will DROP and recreate database '${DB_NAME}'."
  read -r -p "Type '${DB_NAME}' to continue: " confirmation
  if [[ "${confirmation}" != "${DB_NAME}" ]]; then
    echo "[restore] cancelled."
    exit 1
  fi
fi

container_file="/tmp/restore-$(date +%s).dump"

echo "[restore] copying dump into container: ${container_file}"
docker compose cp "${BACKUP_FILE}" "${SERVICE_NAME}:${container_file}"

echo "[restore] terminating active sessions for ${DB_NAME}"
docker compose exec -T "${SERVICE_NAME}" psql -U "${DB_USER}" -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='${DB_NAME}' AND pid <> pg_backend_pid();"

echo "[restore] recreating database: ${DB_NAME}"
docker compose exec -T "${SERVICE_NAME}" psql -U "${DB_USER}" -d postgres -c "DROP DATABASE IF EXISTS ${DB_NAME};"
docker compose exec -T "${SERVICE_NAME}" psql -U "${DB_USER}" -d postgres -c "CREATE DATABASE ${DB_NAME};"

echo "[restore] restoring dump into ${DB_NAME}"
docker compose exec -T "${SERVICE_NAME}" pg_restore -U "${DB_USER}" -d "${DB_NAME}" --clean --if-exists "${container_file}"

echo "[restore] cleaning temporary file"
docker compose exec -T "${SERVICE_NAME}" rm -f "${container_file}"

echo "[restore] done."
