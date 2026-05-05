#!/usr/bin/env bash
set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
MAX_ATTEMPTS="${SMOKE_MAX_ATTEMPTS:-30}"
SLEEP_SECONDS="${SMOKE_SLEEP_SECONDS:-2}"

request_body=""
request_status=""

log() {
  printf '[compose-smoke] %s\n' "$1"
}

fail() {
  printf '[compose-smoke] ERROR: %s\n' "$1" >&2
  if [[ -n "${request_body}" ]]; then
    printf '[compose-smoke] Last response body:\n%s\n' "${request_body}" >&2
  fi
  exit 1
}

request() {
  local path="$1"
  local url="${API_BASE_URL}${path}"
  local response

  response="$(curl --silent --show-error --write-out $'\n%{http_code}' "${url}")"
  request_body="${response%$'\n'*}"
  request_status="${response##*$'\n'}"
}

assert_status() {
  local path="$1"
  local expected_status="$2"

  request "${path}"

  if [[ "${request_status}" != "${expected_status}" ]]; then
    fail "Expected ${path} to return HTTP ${expected_status}, got ${request_status}."
  fi
}

assert_body_contains() {
  local path="$1"
  local expected_text="$2"

  if [[ "${request_body}" != *"${expected_text}"* ]]; then
    fail "Expected ${path} response to contain '${expected_text}'."
  fi
}

wait_for_api() {
  local attempt

  for attempt in $(seq 1 "${MAX_ATTEMPTS}"); do
    if request "/health" && [[ "${request_status}" == "200" ]]; then
      log "API is reachable at ${API_BASE_URL}."
      return 0
    fi

    log "Waiting for API health (${attempt}/${MAX_ATTEMPTS})..."
    sleep "${SLEEP_SECONDS}"
  done

  fail "API did not become healthy at ${API_BASE_URL}/health."
}

check_endpoint() {
  local path="$1"
  local expected_text="$2"

  log "Checking ${path}..."
  assert_status "${path}" "200"
  assert_body_contains "${path}" "${expected_text}"
}

wait_for_api

check_endpoint "/health" '"status":"ok"'
check_endpoint "/ready" '"database":"ok"'
check_endpoint "/products" '"items"'
check_endpoint "/forecasts" '"items"'
check_endpoint "/dashboard/summary" '"summary"'
check_endpoint "/inventory-risks" '"items"'

log "Compose smoke test passed."
