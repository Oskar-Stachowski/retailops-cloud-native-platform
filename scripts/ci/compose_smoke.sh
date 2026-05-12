#!/usr/bin/env bash
set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
FRONTEND_BASE_URL="${FRONTEND_BASE_URL:-http://localhost:3000}"
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

wait_for_frontend() {
  local attempt
  local frontend_status

  for attempt in $(seq 1 "${MAX_ATTEMPTS}"); do
    if frontend_status="$(curl --silent --show-error --output /dev/null --write-out "%{http_code}" "${FRONTEND_BASE_URL}/")" \
      && [[ "${frontend_status}" == "200" ]]; then
      log "Frontend is reachable at ${FRONTEND_BASE_URL}."
      return 0
    fi

    log "Waiting for frontend (${attempt}/${MAX_ATTEMPTS})..."
    sleep "${SLEEP_SECONDS}"
  done

  fail "Frontend did not become reachable at ${FRONTEND_BASE_URL}/."
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

wait_for_frontend

log "Checking frontend root..."
frontend_status="$(curl --silent --show-error --output /dev/null --write-out "%{http_code}" "${FRONTEND_BASE_URL}/")"

if [[ "${frontend_status}" != "200" ]]; then
  fail "Expected frontend root to return HTTP 200, got ${frontend_status}."
fi

log "Checking frontend API proxy /api/health..."
proxy_health_status="$(curl --silent --show-error --output /dev/null --write-out "%{http_code}" "${FRONTEND_BASE_URL}/api/health")"

if [[ "${proxy_health_status}" != "200" ]]; then
  fail "Expected frontend API proxy /api/health to return HTTP 200, got ${proxy_health_status}."
fi

log "Checking frontend API proxy /api/ready..."
proxy_ready_status="$(curl --silent --show-error --output /dev/null --write-out "%{http_code}" "${FRONTEND_BASE_URL}/api/ready")"

if [[ "${proxy_ready_status}" != "200" ]]; then
  fail "Expected frontend API proxy /api/ready to return HTTP 200, got ${proxy_ready_status}."
fi

log "Compose smoke test passed."
