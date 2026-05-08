#!/usr/bin/env bash
set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
PROMETHEUS_BASE_URL="${PROMETHEUS_BASE_URL:-http://localhost:9090}"
GRAFANA_BASE_URL="${GRAFANA_BASE_URL:-http://localhost:3001}"
GRAFANA_ADMIN_USER="${GRAFANA_ADMIN_USER:-admin}"
GRAFANA_ADMIN_PASSWORD="${GRAFANA_ADMIN_PASSWORD:-retailops}"
REPORT_DIR="${OBSERVABILITY_REPORTS_DIR:-ci-cd/reports/observability}"
MAX_ATTEMPTS="${SMOKE_MAX_ATTEMPTS:-30}"
SLEEP_SECONDS="${SMOKE_SLEEP_SECONDS:-2}"

request_body=""
request_status=""

expected_dashboards=(
  "RetailOps Overview"
  "RetailOps API"
  "RetailOps Business Operations"
  "RetailOps Stream Processing"
)

expected_rules=(
  "RetailOpsApiMetricsTargetDown"
  "RetailOpsApiInfoMissing"
  "RetailOpsDatabaseOperationsMissing"
  "RetailOpsStreamEventsStale"
  "RetailOpsStreamDeadLetterEventsIncreasing"
)

expected_metrics=(
  "retailops_api_info"
  "retailops_db_operations_total"
  "retailops_stream_metrics_generated_at_seconds"
)

log() {
  printf '[observability-smoke] %s\n' "$1"
}

fail() {
  printf '[observability-smoke] ERROR: %s\n' "$1" >&2
  if [[ -n "${request_body}" ]]; then
    printf '[observability-smoke] Last response body:\n%s\n' "${request_body}" >&2
  fi
  exit 1
}

request_url() {
  local url="$1"
  shift
  local response

  response="$(curl --silent --show-error --write-out $'\n%{http_code}' "$@" "${url}")"
  request_body="${response%$'\n'*}"
  request_status="${response##*$'\n'}"
}

assert_status() {
  local expected_status="$1"

  if [[ "${request_status}" != "${expected_status}" ]]; then
    fail "Expected HTTP ${expected_status}, got ${request_status}."
  fi
}

assert_body_contains() {
  local expected_text="$1"

  if [[ "${request_body}" != *"${expected_text}"* ]]; then
    fail "Expected response to contain '${expected_text}'."
  fi
}

wait_for_url() {
  local name="$1"
  local url="$2"
  shift 2
  local attempt

  for attempt in $(seq 1 "${MAX_ATTEMPTS}"); do
    if request_url "${url}" "$@" && [[ "${request_status}" == "200" ]]; then
      log "${name} is reachable."
      return 0
    fi

    log "Waiting for ${name} (${attempt}/${MAX_ATTEMPTS})..."
    sleep "${SLEEP_SECONDS}"
  done

  fail "${name} did not become reachable at ${url}."
}

write_report() {
  local file_name="$1"
  local body="$2"

  mkdir -p "${REPORT_DIR}"
  printf '%s\n' "${body}" > "${REPORT_DIR}/${file_name}"
}

wait_for_url "API" "${API_BASE_URL}/health"
wait_for_url "Prometheus" "${PROMETHEUS_BASE_URL}/-/ready"
wait_for_url \
  "Grafana" \
  "${GRAFANA_BASE_URL}/api/health" \
  --user "${GRAFANA_ADMIN_USER}:${GRAFANA_ADMIN_PASSWORD}"

log "Checking API metrics..."
request_url "${API_BASE_URL}/metrics"
assert_status "200"
write_report "api-metrics.txt" "${request_body}"
for metric in "${expected_metrics[@]}"; do
  assert_body_contains "${metric}"
done

log "Checking Prometheus targets..."
request_url "${PROMETHEUS_BASE_URL}/api/v1/targets?state=active"
assert_status "200"
write_report "prometheus-targets.json" "${request_body}"
assert_body_contains '"job":"retailops-api"'
assert_body_contains '"health":"up"'
assert_body_contains '"job":"prometheus"'

log "Checking Prometheus rules..."
request_url "${PROMETHEUS_BASE_URL}/api/v1/rules"
assert_status "200"
write_report "prometheus-rules.json" "${request_body}"
for rule in "${expected_rules[@]}"; do
  assert_body_contains "${rule}"
done

log "Checking Grafana datasource..."
request_url \
  "${GRAFANA_BASE_URL}/api/datasources/uid/retailops-prometheus" \
  --user "${GRAFANA_ADMIN_USER}:${GRAFANA_ADMIN_PASSWORD}"
assert_status "200"
write_report "grafana-prometheus-datasource.json" "${request_body}"
assert_body_contains '"type":"prometheus"'

log "Checking Grafana dashboards..."
request_url \
  "${GRAFANA_BASE_URL}/api/search?query=RetailOps" \
  --user "${GRAFANA_ADMIN_USER}:${GRAFANA_ADMIN_PASSWORD}"
assert_status "200"
write_report "grafana-dashboards.json" "${request_body}"
for dashboard in "${expected_dashboards[@]}"; do
  assert_body_contains "${dashboard}"
done

log "Observability smoke test passed. Evidence saved under ${REPORT_DIR}."
