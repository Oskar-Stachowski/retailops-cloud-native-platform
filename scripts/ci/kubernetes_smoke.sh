#!/usr/bin/env bash
set -euo pipefail

K8S_BASE_DIR="${K8S_BASE_DIR:-k8s/base}"
K8S_DEV_OVERLAY_DIR="${K8S_DEV_OVERLAY_DIR:-k8s/overlays/dev}"
K8S_REPORTS_DIR="${K8S_REPORTS_DIR:-ci-cd/reports/k8s}"
K8S_SMOKE_REPORT="${K8S_SMOKE_REPORT:-${K8S_REPORTS_DIR}/kubernetes-smoke.txt}"
K8S_SMOKE_DRY_RUN="${K8S_SMOKE_DRY_RUN:-0}"

log() {
  printf '[k8s-smoke] %s\n' "$1"
}

fail() {
  printf '[k8s-smoke] ERROR: %s\n' "$1" >&2
  exit 1
}

require_command() {
  local command_name="$1"

  if ! command -v "${command_name}" >/dev/null 2>&1; then
    fail "Required command '${command_name}' is not available."
  fi
}

write_report_header() {
  mkdir -p "${K8S_REPORTS_DIR}"
  {
    printf 'RetailOps Kubernetes smoke test\n'
    printf 'Generated at: %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    printf 'Base path: %s\n' "${K8S_BASE_DIR}"
    printf 'Dev overlay path: %s\n' "${K8S_DEV_OVERLAY_DIR}"
    printf 'Dry-run enabled: %s\n' "${K8S_SMOKE_DRY_RUN}"
    printf '\n'
  } >"${K8S_SMOKE_REPORT}"
}

append_report() {
  printf '%s\n' "$1" >>"${K8S_SMOKE_REPORT}"
}

render_manifests() {
  local source_dir="$1"
  local output_file="$2"

  log "Rendering ${source_dir}..."
  kubectl kustomize "${source_dir}" >"${output_file}"
}

parse_rendered_yaml() {
  local label="$1"
  local rendered_file="$2"

  log "Parsing rendered ${label} YAML..."
  ruby -e 'require "yaml"; YAML.load_stream(File.read(ARGV.fetch(0)))' "${rendered_file}"
  append_report "OK: rendered ${label} YAML parses successfully."
}

assert_rendered_objects() {
  local label="$1"
  local rendered_file="$2"
  shift 2

  log "Checking expected ${label} objects..."
  ruby - "${rendered_file}" "$@" <<'RUBY'
require "yaml"

rendered_file = ARGV.shift
expected = ARGV
documents = YAML.load_stream(File.read(rendered_file)).compact
objects = documents.map do |document|
  metadata = document.fetch("metadata", {})
  "#{document.fetch("kind", "")}/#{metadata.fetch("name", "")}"
end

missing = expected.reject { |object| objects.include?(object) }
unless missing.empty?
  warn "Missing rendered objects: #{missing.join(", ")}"
  exit 1
end
RUBY

  append_report "OK: rendered ${label} contains expected objects: $*."
}

assert_probe_and_resource_coverage() {
  local rendered_file="$1"

  log "Checking Deployment probes and container resource limits..."
  ruby - "${rendered_file}" <<'RUBY'
require "yaml"

deployments = YAML.load_stream(File.read(ARGV.fetch(0))).compact.select do |document|
  document["kind"] == "Deployment"
end

missing_resources = []
missing_probes = []

deployments.each do |deployment|
  name = deployment.fetch("metadata", {}).fetch("name", "unknown")
  pod_spec = deployment.fetch("spec", {}).fetch("template", {}).fetch("spec", {})
  containers = pod_spec.fetch("containers", [])

  containers.each do |container|
    container_name = container.fetch("name", "unknown")
    resources = container.fetch("resources", {})
    requests = resources.fetch("requests", {})
    limits = resources.fetch("limits", {})

    unless requests["cpu"] && requests["memory"] && limits["cpu"] && limits["memory"]
      missing_resources << "#{name}/#{container_name}"
    end

    next unless ["retailops-api", "retailops-frontend", "retailops-realtime-consumer", "postgres", "redpanda"].include?(name)

    unless container["startupProbe"] && container["livenessProbe"] && container["readinessProbe"]
      missing_probes << "#{name}/#{container_name}"
    end
  end
end

unless missing_resources.empty?
  warn "Containers without complete requests/limits: #{missing_resources.join(", ")}"
  exit 1
end

unless missing_probes.empty?
  warn "Containers without startup/liveness/readiness probes: #{missing_probes.join(", ")}"
  exit 1
end
RUBY

  append_report "OK: Deployment containers define resource requests/limits and expected probes."
}

run_optional_dry_run() {
  local rendered_file="$1"

  if [[ "${K8S_SMOKE_DRY_RUN}" != "1" ]]; then
    append_report "SKIP: kubectl server-side dry-run disabled. Set K8S_SMOKE_DRY_RUN=1 to enable it."
    return 0
  fi

  log "Running kubectl server-side dry-run..."
  kubectl apply --dry-run=server -f "${rendered_file}" >>"${K8S_SMOKE_REPORT}"
  append_report "OK: kubectl server-side dry-run passed."
}

require_command kubectl
require_command ruby

base_render="$(mktemp)"
dev_render="$(mktemp)"
trap 'rm -f "${base_render}" "${dev_render}"' EXIT

write_report_header

render_manifests "${K8S_BASE_DIR}" "${base_render}"
parse_rendered_yaml "base" "${base_render}"
assert_rendered_objects \
  "base" \
  "${base_render}" \
  "Namespace/retailops" \
  "ConfigMap/retailops-app-config" \
  "Deployment/retailops-api" \
  "Service/retailops-api" \
  "Deployment/retailops-frontend" \
  "Service/retailops-frontend" \
  "Ingress/retailops-api" \
  "Ingress/retailops-frontend"

render_manifests "${K8S_DEV_OVERLAY_DIR}" "${dev_render}"
parse_rendered_yaml "dev overlay" "${dev_render}"
assert_rendered_objects \
  "dev overlay" \
  "${dev_render}" \
  "Deployment/postgres" \
  "Service/postgres" \
  "Deployment/redpanda" \
  "Service/redpanda" \
  "Deployment/retailops-realtime-consumer" \
  "Job/retailops-migrate" \
  "Job/retailops-seed-demo-data" \
  "Job/redpanda-topic-init"
assert_probe_and_resource_coverage "${dev_render}"
run_optional_dry_run "${dev_render}"

append_report ""
append_report "Kubernetes smoke test passed."
log "Kubernetes smoke test passed. Report: ${K8S_SMOKE_REPORT}"
