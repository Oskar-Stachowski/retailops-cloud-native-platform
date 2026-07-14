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
| GHA-005 | Implemented | `.github/workflows/kubernetes-ci.yml` | Runs Kustomize render, Kubeconform schema validation, Conftest and blocking Checkov policy checks. |
| GHA-008 | Implemented/documented | `.github/workflows/required-ci.yml`, `scripts/ci/detect_required_ci_changes.py`, `docs/governance/branch-protection.md` | Provides one always-running aggregate, `Required CI / required-result`; still requires a GitHub Settings screenshot before claiming enforcement. |
| GHA-009 | Designed/partly implemented | `.github/workflows/terraform-plan.yml`, `docs/ADR/IAM delivery access.md` | Optional Terraform plan uses GitHub OIDC when safe AWS role variable exists. |
| GHA-010 | Implemented | `.github/actions/**` | Composite actions centralize Python setup, Node setup, and CI evidence upload. |
| GHA-011 | Candidate implemented | `.github/workflows/provenance-ci.yml` | Creates GitHub artifact attestations for locally built API/frontend image subjects. |

## Composite action contract

## Required branch-protection gate

`Required CI / required-result` is the only check that should be configured as required on `main`.

The required workflow intentionally does not use workflow-level `paths` filters. It runs for every pull request, every push to `main`, and manual dispatches. A tested Python classifier selects full reusable domain workflows. Shared and unknown paths select every domain gate. A skipped result is valid only when the classifier marked that gate unnecessary; a selected gate must finish with `success`.

The reusable domain workflows are:

- API CI
- Frontend CI
- Docker Compose CI
- Data CI
- Security CI
- Terraform IaC CI
- IaC Security CI
- Kubernetes Policy CI
- Observability CI
- Provenance CI

Observability and provenance remain standalone evidence workflows and are not part of the required merge contract. Playwright is also intentionally excluded from Required CI.

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
| Docker | `ci-cd/reports/docker-compose-ps.txt`, `ci-cd/reports/docker/**`, `ci-cd/reports/observability/**` |
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
- Provenance is implemented as GitHub artifact attestation evidence for local image subjects. Registry push, SBOM attestation, and deployment admission enforcement remain future maturity steps.
