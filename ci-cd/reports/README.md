# CI/CD Reports

This directory is the raw or semi-raw evidence area for machine-generated outputs.

Most files under this directory are ignored because they are volatile, local, large, environment-specific, or may contain sensitive implementation details. Curated reviewer evidence belongs in `docs/evidence/`; sanitized report snapshots may stay here when they are small, useful, and indexed.

## Tracking Policy

| File type | Default policy | Notes |
|---|---|---|
| `README.md` and `*.evidence.md` | Track | Human-readable indexes and curated report notes. |
| `*-snapshot.txt` and `*-snapshot.json` | Track when sanitized | Use for small, stable evidence snapshots. |
| `ci-cd/reports/iac/sprint-*-terraform-*.txt` | Track when sanitized | Used for controlled Terraform showcase evidence. |
| Coverage XML, local logs, generated datasets | Ignore | Regenerate from CI or local commands. |
| Raw scanner JSON such as `gitleaks.json` | Ignore by default | Track only after sanitization or conversion to a reviewer-safe snapshot. |
| Terraform state, binary plans, caches | Never track | These may contain environment-specific or sensitive data. |

## Current Tracked Snapshots

| Path | Purpose |
|---|---|
| `ci-cd/reports/iac/sprint-10-terraform-validate.txt` | Terraform validation snapshot. |
| `ci-cd/reports/iac/sprint-10-terraform-plan-dev.txt` | Sanitized Terraform plan summary. |
| `ci-cd/reports/iac/sprint-10-terraform-apply.txt` | Sanitized Terraform apply summary. |
| `ci-cd/reports/iac/sprint-10-terraform-destroy.txt` | Sanitized Terraform destroy summary. |
| `ci-cd/reports/k8s/kubernetes-smoke-snapshot.txt` | Kubernetes Kustomize render, kubeconform and smoke validation snapshot. |
| `ci-cd/reports/k8s/kubernetes-secret-scan-snapshot.txt` | Kubernetes manifest secret scan snapshot. |
| `ci-cd/reports/security/trivy-fs-snapshot.txt` | Trivy filesystem scan snapshot. |
| `ci-cd/reports/security/trivy-api-image-snapshot.txt` | Trivy API image scan snapshot. |
| `ci-cd/reports/security/trivy-frontend-image-snapshot.txt` | Trivy frontend image scan snapshot. |

## Promotion Rule

Before promoting a local report to tracked evidence:

1. Remove secrets, account IDs, private URLs, resource IDs, and personal data.
2. Prefer a short snapshot or summary over a full raw log.
3. Name the file predictably with `*-snapshot.*` or `*.evidence.md`.
4. Link it from `docs/evidence/index.md`.
5. Record limitations and freshness notes.

## Evidence Refresh Workflow

Use this workflow when a tracked CI/CD report, screenshot, or snapshot is stale:

| Evidence area | Refresh command or source | Expected outcome | Tracked destination |
|---|---|---|---|
| Docker / full-stack smoke | `make compose-ci` | Images build, stack starts, smoke checks pass, cleanup completes. | `docs/evidence/docker/compose-ci-smoke.md` |
| API startup / contract proof | Run the Uvicorn command in `docs/evidence/api/startup-log.md` plus the listed `curl` checks. | API starts and serves `/health` and `/openapi.json`. | `docs/evidence/api/startup-log.md`, `docs/evidence/api/openapi-snapshot.json` |
| Observability local proof | `make observability-smoke` against the running local stack | Prometheus, Grafana, targets, rules, and dashboards respond successfully. | `ci-cd/reports/observability/` plus any curated note added under `docs/evidence/` |
| Kubernetes validation | `make k8s-smoke` | Base and dev manifests render and pass validation. | `ci-cd/reports/k8s/kubernetes-smoke-snapshot.txt` |
| Security snapshots | `make security-scan` | Secret scan and vulnerability scans complete. | `ci-cd/reports/security/*-snapshot.txt` |
| Terraform showcase snapshots | `make terraform-validate`, `make terraform-plan-dev`, or documented showcase apply/destroy flow | Validation or sanitized plan/apply/destroy evidence is captured. | `ci-cd/reports/iac/` |

After refreshing one of these artifacts, update the corresponding row in `docs/evidence/index.md` with the date, commit SHA, command, expected outcome, and artifact path.
