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
