#!/usr/bin/env bash
set -euo pipefail

# Resets ONLY the "public" schema inside a Postgres container (destructive).
# - Drops public schema CASCADE (tables + enum/types + views + functions + sequences).
# - Recreates public schema.
# - Does NOT run migrations (run Alembic manually afterwards).
#
# Usage:
#   scripts/db_reset_public_schema.sh
#   PG_SERVICE=db PGUSER=postgres PGDATABASE=erp scripts/db_reset_public_schema.sh
#
# Requirements:
# - docker compose available
# - the service has psql installed (official postgres images do)

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SQL_FILE="${ROOT_DIR}/scripts/sql/reset_public_schema.sql"

PG_SERVICE="${PG_SERVICE:-db}"
PGUSER="${PGUSER:-postgres}"
PGDATABASE="${PGDATABASE:-erp}"

if [[ ! -f "${SQL_FILE}" ]]; then
  echo "SQL file not found: ${SQL_FILE}" >&2
  exit 1
fi

echo "About to RESET public schema (CASCADE)."
echo "- docker compose service: ${PG_SERVICE}"
echo "- database: ${PGDATABASE}"
echo "- user: ${PGUSER}"
echo "- sql: ${SQL_FILE}"
echo
read -r -p "Type 'RESET' to continue: " CONFIRM
if [[ "${CONFIRM}" != "RESET" ]]; then
  echo "Aborted."
  exit 2
fi

docker compose exec -T "${PG_SERVICE}" \
  psql -v ON_ERROR_STOP=1 -U "${PGUSER}" -d "${PGDATABASE}" \
  -f "/dev/stdin" < "${SQL_FILE}"

echo "Done. Now run Alembic migrations manually."

