# GitHub Actions CI Governance

## Scope

This document maps the RetailOps GitHub Actions implementation to the production-readiness checklist for GitHub Actions CI.

## Implemented workflow coverage

| ID | Status after patch | Evidence path / workflow | Notes |
|---|---|---|---|
| GHA-001 | Implemented | `.github/workflows/api-ci.yml` | Runs backend quality gates, data validation, migrations, seed, DB-backed tests, coverage, and API image build. |
| GHA-002 | Implemented | `.github/workflows/frontend-ci.yml` | Runs frontend tests, lint, production build, and frontend image build. |
| GHA-003 | Implemented | `.github/workflows/docker-ci.yml` | Validates Compose config/profiles and runs full-stack Compose smoke tests. |
| GHA-004 | Implemented | `.github/workflows/security-ci.yml` | Runs secret scan, Trivy filesystem scan, dependency audits, image scans, and consolidated evidence summary. |
| GHA-005 | Implemented | `.github/workflows/kubernetes-ci.yml` | Runs Kustomize, Kubeconform, Conftest and blocking Checkov, followed by an isolated kind deployment with browser/API, NetworkPolicy, streaming, persistence and rollback checks. |
| GHA-008 | Implemented and configured | `.github/workflows/required-ci.yml`, `scripts/ci/detect_required_ci_changes.py`, `docs/evidence/github/README.md` | The aggregate `Required CI / required-result` is required on `main`, including for administrators. Active settings were verified through the GitHub API on 2026-09-25. |
| GHA-009 | Implemented plan path; S3 activation pending | `.github/workflows/terraform-validation.yml`, `.github/workflows/terraform-plan.yml`, `scripts/terraform/` | Required CI verifies backend controls and real local drift/migration without AWS. Manual main-only OIDC plans pin the account, distinguish baseline from existing-state drift and upload sanitized summaries. The prepared S3/KMS backend is not deployed. |
| GHA-010 | Implemented | `.github/actions/**` | Composite actions centralize Python setup, Node setup, and CI evidence upload. |
| GHA-011 | Candidate implemented | `.github/workflows/provenance-ci.yml` | Creates GitHub artifact attestations for locally built API/frontend image subjects. |

## Composite action contract

## Required branch-protection gate

`Required CI / required-result` is the only required aggregate on `main`.
Its exact check context is `required-result`, bound to GitHub Actions app ID
`15368`. Pull requests must be up to date and conversations resolved before
merge. See [the active policy](branch-protection.md).

The required workflow intentionally does not use workflow-level `paths` filters. It runs for every pull request, every push to `main`, and manual dispatches. A tested Python classifier selects full reusable domain workflows. Shared and unknown paths select every domain gate. A skipped result is valid only when the classifier marked that gate unnecessary; a selected gate must finish with `success`.

The reusable domain workflows are invoked automatically only by Required CI and
can also be started manually for standalone evidence:

- API CI
- Frontend CI
- Docker Compose CI
- Data CI
- Security CI
- Terraform Validation CI
- IaC Security CI
- Kubernetes Policy CI

Terraform State and Drift Review is a separate manual-only workflow and is not part of the
required merge contract. Observability and provenance remain standalone
evidence workflows. Docker Compose CI runs the seven critical Chromium browser
journeys against its fresh seeded stack before cleanup. Browser failures fail
the Docker gate and therefore `required-result`. Screenshot evidence capture
remains a separate opt-in Playwright project.

The same Docker gate also runs `make db-recovery-drill` in a separate disposable
Compose project. A failed restore, data/history comparison, application check
or cleanup fails the gate. The report and command log are uploaded with Compose
evidence; database dumps and raw decision payloads are excluded.

It also runs `make release-drill`: immutable image manifests, migration refusal
checks, version update, a controlled API outage and rollback to the original
images, followed by HTTP, browser and full-data checks. Release JSON/logs and
browser failure evidence join the same artifact. See the
[release policy](releases.md) and [rollback runbook](../runbooks/application-rollback.md).

| Changed area | Full workflows selected by Required CI |
|---|---|
| API | API, Docker Compose, Security |
| Frontend | Frontend, Docker Compose, Security |
| Data/events/ML data | Data, API, Docker Compose, Security |
| Docker/Compose | Docker Compose, Security |
| Terraform/IaC | Terraform validation, IaC Security |
| Kubernetes | Kubernetes Policy, Security |
| Policy | Kubernetes Policy, Security |
| Documentation only | Contract tests and diff hygiene only |
| Shared or unknown | API, Frontend, Data, Docker Compose, Terraform, IaC Security, Kubernetes Policy, Security |

| Composite action | Purpose |
|---|---|
| `.github/actions/setup-python-ci` | Standard Python setup, pip cache, optional dependency install. |
| `.github/actions/setup-node-ci` | Standard Node setup, npm cache, optional dependency install. |
| `.github/actions/upload-ci-evidence` | Standard artifact upload with consistent retention and missing-file behavior. |

These actions are intentionally small. They reduce duplication without hiding business-specific test commands inside generic abstractions.

## Evidence artifact convention

Runtime evidence should be uploaded from paths under:

```text
ci-cd/reports/**
```

Current workflow artifact families:

| Area | Example evidence paths |
|---|---|
| API | `ci-cd/reports/api/coverage.xml`, `ci-cd/reports/security/bandit-api.txt` |
| Data | `ci-cd/reports/data/**`, `docs/evidence/data/scenario-coverage-report.md` |
| Frontend | `ci-cd/reports/frontend/test.txt`, `ci-cd/reports/frontend/lint.txt`, `ci-cd/reports/frontend/build.txt` |
| Docker | `ci-cd/reports/docker-compose-ps.txt`, `ci-cd/reports/docker/**`, `ci-cd/reports/observability/**`, `ci-cd/reports/e2e/**` |
| Security | `ci-cd/reports/security/trivy-fs.txt`, `pip-audit.json`, `npm-audit.json`, image scan reports |
| IaC | `ci-cd/reports/iac/terraform-validate.txt`, `tflint.txt`, `checkov.txt`, `checkov.json` |
| Provenance | `ci-cd/reports/provenance/provenance-summary.md` |

## Manual validation commands

Recommended local commands before opening or merging a PR:

```bash
make ci-local
make compose-ci
```

Targeted validation:

```bash
make data-quality data-contracts data-scenario-report
make terraform-fmt-check terraform-validate
make tflint-report checkov-scan
make k8s-ci
python3 scripts/ci/test_detect_required_ci_changes.py
```

GitHub-side validation:

```bash
# Install actionlint locally if available, then run:
actionlint
```

## Known boundaries

- Branch protection cannot be proven by repository code alone. It needs a GitHub Settings screenshot or exported settings evidence.
- The optional Terraform plan job needs a safe `AWS_TERRAFORM_PLAN_ROLE_ARN` repository variable and an OIDC role configured in AWS.
- The standalone Provenance CI retains its local-image scope. The manual
  [registry release workflow](releases.md) publishes tested image digests, signs
  their provenance/SBOMs and verifies them on a fresh runner before promoting a
  release. Deployment admission enforcement remains a future step.
