#!/usr/bin/env bash
set -euo pipefail

# Creates/updates an ERP superuser (docker or local).
#
# Fixed user:
# - email: erp@bdf.kr
# - full_name: 관리자
# - is_superuser: true
#
# Password is requested interactively (not echoed).
#
# Usage:
#   scripts/create_superuser.sh
#   BACKEND_SERVICE=backend scripts/create_superuser.sh
#
# Local mode requirements:
# - Run from repo root (or adjust paths)
# - uv installed

BACKEND_SERVICE="${BACKEND_SERVICE:-backend}"

read -r -p "Run mode [docker/local] (default: docker): " MODE
MODE="${MODE:-docker}"
if [[ "${MODE}" != "docker" && "${MODE}" != "local" ]]; then
  echo "Invalid mode: ${MODE} (expected docker or local)" >&2
  exit 1
fi

read -r -p "Superuser email (fixed): erp@bdf.kr. Continue? [y/N] " OK
if [[ "${OK}" != "y" && "${OK}" != "Y" ]]; then
  echo "Aborted."
  exit 2
fi

read -r -s -p "Enter password: " SUPERUSER_PASSWORD
echo
read -r -s -p "Confirm password: " SUPERUSER_PASSWORD_CONFIRM
echo

if [[ "${SUPERUSER_PASSWORD}" != "${SUPERUSER_PASSWORD_CONFIRM}" ]]; then
  echo "Passwords do not match." >&2
  exit 1
fi

if [[ "${#SUPERUSER_PASSWORD}" -lt 8 ]]; then
  echo "Password must be at least 8 characters." >&2
  exit 1
fi

if [[ "${MODE}" == "docker" ]]; then
  docker compose exec -T "${BACKEND_SERVICE}" \
    env SUPERUSER_PASSWORD="${SUPERUSER_PASSWORD}" \
    python -m app.commands.create_superuser
else
  (
    cd "$(dirname "${BASH_SOURCE[0]}")/../fastapi_backend"
    SUPERUSER_PASSWORD="${SUPERUSER_PASSWORD}" uv run python -m app.commands.create_superuser
  )
fi

echo "Done."

