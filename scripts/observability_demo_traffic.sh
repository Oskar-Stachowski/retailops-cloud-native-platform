#!/usr/bin/env bash
set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
PROMETHEUS_BASE_URL="${PROMETHEUS_BASE_URL:-http://localhost:9090}"
GRAFANA_BASE_URL="${GRAFANA_BASE_URL:-http://localhost:3001}"
GRAFANA_ADMIN_USER="${GRAFANA_ADMIN_USER:-admin}"
GRAFANA_ADMIN_PASSWORD="${GRAFANA_ADMIN_PASSWORD:-retailops}"
COMPOSE="${COMPOSE:-docker compose}"
REPORT_DIR="${OBSERVABILITY_REPORTS_DIR:-ci-cd/reports/observability}"
MAX_ATTEMPTS="${SMOKE_MAX_ATTEMPTS:-30}"
SLEEP_SECONDS="${SMOKE_SLEEP_SECONDS:-2}"
PROMETHEUS_SCRAPE_WAIT_SECONDS="${PROMETHEUS_SCRAPE_WAIT_SECONDS:-18}"

request_body=""
request_status=""

log() {
  printf '[observability-demo] %s\n' "$1"
}

fail() {
  printf '[observability-demo] ERROR: %s\n' "$1" >&2
  if [[ -n "${request_body}" ]]; then
    printf '[observability-demo] Last response body:\n%s\n' "${request_body}" >&2
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

call_api() {
  local path="$1"
  local correlation_id="$2"

  request_url "${API_BASE_URL}${path}" --header "X-Correlation-ID: ${correlation_id}"
  if [[ "${request_status}" != "200" ]]; then
    fail "Expected ${path} to return HTTP 200, got ${request_status}."
  fi
}

call_api_optional() {
  local path="$1"
  local correlation_id="$2"

  request_url "${API_BASE_URL}${path}" --header "X-Correlation-ID: ${correlation_id}"
  if [[ "${request_status}" != "200" ]]; then
    log "Optional signal ${path} returned HTTP ${request_status}; continuing."
  fi
}

extract_product_ids() {
  python3 -c '
import json
import sys

payload = json.load(sys.stdin)
items = payload.get("items", [])
for item in items[:3]:
    product_id = item.get("id")
    if product_id:
        print(product_id)
'
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

log "Loading demo products..."
request_url "${API_BASE_URL}/products?limit=3&sort_by=sku&sort_order=asc"
if [[ "${request_status}" != "200" ]]; then
  fail "Could not load demo products."
fi

product_ids=()
while IFS= read -r product_id; do
  product_ids+=("${product_id}")
done < <(printf '%s\n' "${request_body}" | extract_product_ids)
if [[ "${#product_ids[@]}" -eq 0 ]]; then
  fail "No product IDs found. Run make observability-up first so demo data is seeded."
fi

log "Generating correlated API traffic..."
for round in 1 2 3; do
  correlation_id="obs-demo-api-round-${round}"

  call_api "/dashboard/summary" "${correlation_id}"
  call_api_optional "/dashboard/operational-visibility?sales_trend_days=14&work_items_limit=10" "${correlation_id}"
  call_api "/dashboard/live-operations?window_minutes=60&recent_events_limit=20&alerts_limit=10" "${correlation_id}"
  call_api "/dashboard/sales-trend?days=14" "${correlation_id}"
  call_api "/dashboard/stock-risk-summary" "${correlation_id}"
  call_api "/products?limit=20&sort_by=sku&sort_order=asc" "${correlation_id}"
  call_api "/forecasts?limit=20&sort_by=forecast_period_start&sort_order=desc" "${correlation_id}"
  call_api "/inventory-snapshots?limit=20&sort_by=recorded_at&sort_order=desc" "${correlation_id}"
  call_api "/inventory-risks?limit=20&sort_by=risk_status&sort_order=asc" "${correlation_id}"
  call_api "/sales?limit=20&sort_by=sold_at&sort_order=desc" "${correlation_id}"

  for product_id in "${product_ids[@]}"; do
    call_api "/products/${product_id}" "${correlation_id}"
    call_api_optional "/products/${product_id}/360?limit=5" "${correlation_id}"
    call_api "/forecasts?product_id=${product_id}&limit=5" "${correlation_id}"
    call_api "/inventory-snapshots?product_id=${product_id}&limit=5" "${correlation_id}"
    call_api "/sales?product_id=${product_id}&limit=5" "${correlation_id}"
  done
done

log "Generating realistic stream/business events inside the API container..."
mkdir -p "${REPORT_DIR}"
${COMPOSE} exec -T api env PYTHONPATH=/app python scripts/generate_observability_demo_events.py \
  > "${REPORT_DIR}/observability-demo-events.json" \
  2> "${REPORT_DIR}/observability-demo-events-errors.log"

log "Forcing a metrics scrape path..."
request_url "${API_BASE_URL}/metrics"
if [[ "${request_status}" != "200" ]]; then
  fail "Expected /metrics to return HTTP 200, got ${request_status}."
fi
write_report "api-metrics-after-demo.txt" "${request_body}"

log "Waiting ${PROMETHEUS_SCRAPE_WAIT_SECONDS}s for Prometheus to scrape the new metrics..."
sleep "${PROMETHEUS_SCRAPE_WAIT_SECONDS}"

request_url "${PROMETHEUS_BASE_URL}/api/v1/query?query=retailops_stream_events_total"
if [[ "${request_status}" != "200" ]]; then
  fail "Expected Prometheus query to return HTTP 200, got ${request_status}."
fi
write_report "prometheus-stream-events-query.json" "${request_body}"

request_url "${PROMETHEUS_BASE_URL}/api/v1/query?query=retailops_stream_dlq_events_total"
if [[ "${request_status}" != "200" ]]; then
  fail "Expected Prometheus DLQ query to return HTTP 200, got ${request_status}."
fi
write_report "prometheus-dlq-events-query.json" "${request_body}"

request_url "${PROMETHEUS_BASE_URL}/api/v1/query?query=retailops_db_operations_total"
if [[ "${request_status}" != "200" ]]; then
  fail "Expected Prometheus DB query to return HTTP 200, got ${request_status}."
fi
write_report "prometheus-db-operations-query.json" "${request_body}"

log "Demo traffic completed."
log "Interpretation hints:"
log "- API dashboard: DB operation totals should rise after the correlated request rounds."
log "- Business dashboard: live revenue, units sold, stock delta, alerts and anomalies should be non-zero."
log "- Stream dashboard: processed, ignored duplicate and dead-letter event counts should be visible."
log "- Evidence saved under ${REPORT_DIR}."
