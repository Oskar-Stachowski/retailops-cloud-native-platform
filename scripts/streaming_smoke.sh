#!/usr/bin/env bash
set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
PROMETHEUS_BASE_URL="${PROMETHEUS_BASE_URL:-http://localhost:9090}"
COMPOSE="${COMPOSE:-docker compose}"
MAX_ATTEMPTS="${SMOKE_MAX_ATTEMPTS:-30}"
SLEEP_SECONDS="${SMOKE_SLEEP_SECONDS:-2}"

request_body=""
request_status=""

expected_topics=(
  "retailops.sales.v1"
  "retailops.inventory.v1"
  "retailops.pricing.v1"
  "retailops.intelligence.v1"
  "retailops.operations.v1"
  "retailops.dlq.v1"
)

expected_metrics=(
  "retailops_stream_latest_event_present"
  "retailops_stream_event_freshness_seconds"
  "retailops_stream_processing_latency_seconds_avg"
  "retailops_stream_processing_latency_seconds_max"
  "retailops_stream_metrics_generated_at_seconds"
)

expected_alerts=(
  "RetailOpsApiMetricsTargetDown"
  "RetailOpsStreamNoEventsIngested"
  "RetailOpsStreamEventsStale"
  "RetailOpsStreamDeadLetterEventsIncreasing"
  "RetailOpsStreamConsumerFailuresIncreasing"
  "RetailOpsStreamConsumerLagHigh"
  "RetailOpsStreamConsumerLagCritical"
  "RetailOpsStreamConsumerDown"
  "RetailOpsStreamConsumerMissing"
  "RetailOpsStreamProcessingLatencyHigh"
  "RetailOpsStreamProcessingLatencyCritical"
)

log() {
  printf '[streaming-smoke] %s\n' "$1"
}

fail() {
  printf '[streaming-smoke] ERROR: %s\n' "$1" >&2
  if [[ -n "${request_body}" ]]; then
    printf '[streaming-smoke] Last response body:\n%s\n' "${request_body}" >&2
  fi
  exit 1
}

request_url() {
  local url="$1"
  local response

  response="$(curl --silent --show-error --write-out $'\n%{http_code}' "${url}")"
  request_body="${response%$'\n'*}"
  request_status="${response##*$'\n'}"
}

request_api() {
  local path="$1"
  request_url "${API_BASE_URL}${path}"
}

request_prometheus() {
  local path="$1"
  request_url "${PROMETHEUS_BASE_URL}${path}"
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

wait_for_api() {
  local attempt

  for attempt in $(seq 1 "${MAX_ATTEMPTS}"); do
    if request_api "/health" && [[ "${request_status}" == "200" ]]; then
      log "API is reachable at ${API_BASE_URL}."
      return 0
    fi

    log "Waiting for API health (${attempt}/${MAX_ATTEMPTS})..."
    sleep "${SLEEP_SECONDS}"
  done

  fail "API did not become healthy at ${API_BASE_URL}/health."
}

wait_for_prometheus() {
  local attempt

  for attempt in $(seq 1 "${MAX_ATTEMPTS}"); do
    if request_prometheus "/-/ready" && [[ "${request_status}" == "200" ]]; then
      log "Prometheus is reachable at ${PROMETHEUS_BASE_URL}."
      return 0
    fi

    log "Waiting for Prometheus readiness (${attempt}/${MAX_ATTEMPTS})..."
    sleep "${SLEEP_SECONDS}"
  done

  fail "Prometheus did not become ready at ${PROMETHEUS_BASE_URL}/-/ready."
}

check_broker_topics() {
  local attempt
  local topic
  local topics

  for attempt in $(seq 1 "${MAX_ATTEMPTS}"); do
    log "Checking Redpanda topics (${attempt}/${MAX_ATTEMPTS})..."
    if topics="$(${COMPOSE} exec -T redpanda rpk topic list --brokers redpanda:9092 2>/dev/null)"; then
      for topic in "${expected_topics[@]}"; do
        if [[ "${topics}" != *"${topic}"* ]]; then
          sleep "${SLEEP_SECONDS}"
          continue 2
        fi
      done

      return 0
    fi

    sleep "${SLEEP_SECONDS}"
  done

  fail "Expected all Sprint 9 Redpanda topics to exist."
}

check_live_operations_endpoint() {
  log "Checking live operations API..."
  request_api "/dashboard/live-operations?window_minutes=15&recent_events_limit=5&alerts_limit=5"
  assert_status "200"
  assert_body_contains '"metrics"'
  assert_body_contains '"event_status_counts"'
  assert_body_contains '"freshness"'
  assert_body_contains '"consumer_states"'
}

check_metrics_endpoint() {
  local metric

  log "Checking stream metrics endpoint..."
  request_api "/metrics"
  assert_status "200"

  for metric in "${expected_metrics[@]}"; do
    assert_body_contains "${metric}"
  done
}

check_prometheus_targets() {
  local attempt

  for attempt in $(seq 1 "${MAX_ATTEMPTS}"); do
    log "Checking Prometheus target health (${attempt}/${MAX_ATTEMPTS})..."
    request_prometheus "/api/v1/targets?state=active"
    assert_status "200"

    if [[ "${request_body}" == *'"job":"retailops-api"'* ]] \
      && [[ "${request_body}" == *'"health":"up"'* ]]; then
      return 0
    fi

    sleep "${SLEEP_SECONDS}"
  done

  fail "Expected Prometheus to report the retailops-api target as up."
}

check_prometheus_rules() {
  local alert

  log "Checking Prometheus stream alert rules..."
  request_prometheus "/api/v1/rules"
  assert_status "200"

  for alert in "${expected_alerts[@]}"; do
    assert_body_contains "${alert}"
  done
}

wait_for_api
wait_for_prometheus
check_broker_topics
check_live_operations_endpoint
check_metrics_endpoint
check_prometheus_targets
check_prometheus_rules

log "Streaming smoke test passed."
