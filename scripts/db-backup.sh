#!/usr/bin/env bash
# bash scripts/db-backup.sh
set -euo pipefail

SERVICE_NAME="${SERVICE_NAME:-db}"
DB_USER="${DB_USER:-postgres}"
DB_NAME="${DB_NAME:-erp}"
BACKUP_DIR="${BACKUP_DIR:-./db_backups}"
TIMESTAMP="$(date +%F-%H%M%S)"
OUT_FILE="${1:-${BACKUP_DIR}/${DB_NAME}-${TIMESTAMP}.dump}"

mkdir -p "${BACKUP_DIR}"

tmp_file="/tmp/${DB_NAME}-${TIMESTAMP}.dump"

log() {
  echo "[$(date '+%F %T %z')] $*"
}

log "[backup] creating dump inside container: ${tmp_file}"
docker compose exec -T "${SERVICE_NAME}" pg_dump -U "${DB_USER}" -d "${DB_NAME}" -F c -f "${tmp_file}"

log "[backup] copying dump to host: ${OUT_FILE}"
docker compose cp "${SERVICE_NAME}:${tmp_file}" "${OUT_FILE}"

log "[backup] cleaning temporary file"
docker compose exec -T "${SERVICE_NAME}" rm -f "${tmp_file}"

log "[backup] done: ${OUT_FILE}"
