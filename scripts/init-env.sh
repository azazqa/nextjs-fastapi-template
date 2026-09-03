#!/usr/bin/env bash
# Create root and backend .env from examples with random secrets.
# Prompts before overwriting an existing file (default: No).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${ROOT_DIR}/fastapi_backend"

confirm_overwrite() {
  local path="$1"
  if [[ ! -f "$path" ]]; then
    return 0
  fi
  local reply
  read -r -p "Overwrite ${path}? [y/N] " reply
  case "${reply}" in
    y|Y|yes|YES) return 0 ;;
    *)
      echo "Kept existing ${path}"
      return 1
      ;;
  esac
}

write_root_env() {
  local dest="${ROOT_DIR}/.env"
  if ! confirm_overwrite "$dest"; then
    return 0
  fi
  local project_name password
  project_name="$(basename "${ROOT_DIR}")"
  password="$(openssl rand -hex 32)"
  sed \
    -e "s|__POSTGRES_PASSWORD__|${password}|" \
    -e "s|__PROJECT_NAME__|${project_name}|" \
    -e "s|^COMPOSE_PROJECT_NAME=.*|COMPOSE_PROJECT_NAME=${project_name}|" \
    "${ROOT_DIR}/.env.example" >"${dest}"
  echo "Created ${dest}"
}

write_backend_env() {
  local dest="${BACKEND_DIR}/.env"
  if ! confirm_overwrite "$dest"; then
    return 0
  fi
  local access reset verify refresh
  access="$(openssl rand -hex 32)"
  reset="$(openssl rand -hex 32)"
  verify="$(openssl rand -hex 32)"
  refresh="$(openssl rand -hex 32)"
  sed \
    -e "s|your_access_secret_key|${access}|" \
    -e "s|your_reset_password_secret_key|${reset}|" \
    -e "s|your_verification_secret_key|${verify}|" \
    -e "s|your_refresh_secret_key|${refresh}|" \
    "${BACKEND_DIR}/.env.example" >"${dest}"
  echo "Created ${dest}"
}

write_root_env
write_backend_env
echo "Done. If you rotated POSTGRES_PASSWORD, update the running DB (ALTER USER) to match."
