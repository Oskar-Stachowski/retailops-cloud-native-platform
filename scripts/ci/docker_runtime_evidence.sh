#!/usr/bin/env bash
set -euo pipefail

COMPOSE="${COMPOSE:-docker compose}"
DOCKER_REPORTS_DIR="${DOCKER_REPORTS_DIR:-ci-cd/reports/docker}"
COMPOSE_PROFILE_SET="${COMPOSE_PROFILE_SET:-dev test observability security}"
API_IMAGE="${API_IMAGE:-retailops-api:0.1.0}"
FRONTEND_IMAGE="${FRONTEND_IMAGE:-retailops-frontend:0.1.0}"

log() {
  printf '[docker-runtime-evidence] %s\n' "$1"
}

fail() {
  printf '[docker-runtime-evidence] ERROR: %s\n' "$1" >&2
  exit 1
}

require_command() {
  local command_name="$1"
  command -v "${command_name}" >/dev/null 2>&1 || fail "${command_name} is not installed or not available in PATH."
}

inspect_image_user() {
  local image="$1"
  local expected_user="$2"
  local actual_user

  actual_user="$(docker image inspect "${image}" --format '{{.Config.User}}')"
  printf '%s user=%s expected=%s\n' "${image}" "${actual_user}" "${expected_user}" >> "${DOCKER_REPORTS_DIR}/image-users.txt"

  if [[ -z "${actual_user}" || "${actual_user}" == "0" || "${actual_user}" == "root" ]]; then
    fail "${image} runs as root or does not declare a non-root user. Actual user: '${actual_user}'."
  fi
}

mkdir -p "${DOCKER_REPORTS_DIR}"
: > "${DOCKER_REPORTS_DIR}/image-users.txt"

require_command docker

log "Validating Compose profiles: ${COMPOSE_PROFILE_SET}"
for profile in ${COMPOSE_PROFILE_SET}; do
  log "Rendering profile: ${profile}"
  COMPOSE_PROFILES="${profile}" ${COMPOSE} config > "${DOCKER_REPORTS_DIR}/compose-profile-${profile}.yml"
done

log "Building runtime images used by docker-compose.yml"
COMPOSE_PROFILES=dev ${COMPOSE} build api frontend

log "Inspecting runtime image users"
inspect_image_user "${API_IMAGE}" "appuser"
inspect_image_user "${FRONTEND_IMAGE}" "101:101"

log "Capturing current Compose service state"
${COMPOSE} ps > "${DOCKER_REPORTS_DIR}/docker-compose-ps.txt" || true

log "Evidence written to ${DOCKER_REPORTS_DIR}"
