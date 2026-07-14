# GitHub Branch Protection Policy

## Purpose

This document defines the expected GitHub branch protection settings for the RetailOps repository. It is reviewer-facing evidence for the GitHub Actions CI workstream and explains which checks should block merges before code reaches `main`.

The policy is intentionally documented in the repository because GitHub branch protection itself is configured in repository settings and cannot be fully enforced by ordinary application code.

## Protected branch

| Setting | Expected value |
|---|---|
| Protected branch pattern | `main` |
| Merge model | Pull request before merge |
| Direct pushes to `main` | Disabled for normal development |
| Force pushes | Disabled |
| Branch deletion | Disabled |
| Required review | At least 1 approving review for portfolio/reviewer mode |
| Stale approvals | Dismiss stale approvals when new commits are pushed |
| Conversation resolution | Required before merge |
| Administrator bypass | Avoid for normal project work; document any exception |

## Required status checks

Configure only this stable required check once the first successful `Required CI` run is available:

| Workflow | Required check / job | Why it matters |
|---|---|---|
| Required CI | `Required CI / required-result` | Always runs for every PR, every push to `main`, and manual dispatch. It calls the existing full domain workflows selected by tested path detection and fails if a required workflow is skipped, cancelled or unsuccessful. |

Do not configure the path-filtered domain workflows as separate required branch protection checks. `Required CI` invokes those same workflows through `workflow_call`, while their direct path-filtered triggers remain useful for standalone evidence. The stable `required-result` job verifies the expected-versus-actual result of every called workflow.

Optional checks, depending on current sprint scope:

| Workflow | Check | When to require |
|---|---|---|
| API CI | `API integration tests`, `API Docker image build` | Called by Required CI for API/data/shared/unknown changes. |
| Frontend CI | `Frontend tests and lint`, `Build frontend application`, `Build frontend Docker image` | Called by Required CI for frontend/shared/unknown changes. |
| Docker Compose CI | `Validate Docker Compose config`, `Build full stack and run smoke tests` | Called by Required CI for application, data, Compose, shared and unknown changes. |
| Security CI | Security scan jobs and `Security evidence summary` | Called with explicit blocking thresholds for application, Compose, Kubernetes, policy, security, shared and unknown changes. |
| Data CI | `Synthetic data quality gate` | Called by Required CI for data/shared/unknown changes. |
| Terraform IaC CI | `Terraform fmt, init and validate` | Called by Required CI for Terraform/shared/unknown changes. |
| IaC Security CI | `TFLint IaC quality gate`, `Checkov IaC security report` | Called by Required CI together with Terraform validation; Checkov is blocking outside documented exceptions. |
| Kubernetes Policy CI | `Kustomize, schema and policy gates` | Called for Kubernetes/policy/shared/unknown changes; runs Kustomize, Kubeconform, Conftest and Checkov. |
| Observability CI | `Validate observability assets` | Require once observability assets are in active scope |
| Provenance CI | `Build local images and generate provenance attestations` | Require for release branches or signed release candidate evidence, not necessarily every PR |
| Terraform IaC CI | `Optional dev Terraform plan` | Manual-only; do not require on normal PRs unless safe AWS OIDC credentials are configured |

## Evidence collection

For every CI-related portfolio claim, collect at least one of the following:

- screenshot of a green workflow run;
- link to a successful GitHub Actions run;
- downloaded artifact from `ci-cd/reports/**`;
- screenshot of branch protection settings showing required checks;
- short note in `docs/evidence/index.md` describing what changed and when evidence was refreshed.

## Reviewer checklist

Before claiming branch protection as implemented:

- [ ] `main` is protected in GitHub repository settings.
- [ ] Pull requests are required before merging.
- [ ] Direct pushes and force pushes are blocked.
- [ ] Required checks include only `Required CI / required-result`.
- [ ] At least one green `Required CI / required-result` run exists.
- [ ] A screenshot or reviewer-visible note is stored under `docs/evidence/` or referenced in the evidence ledger.

## CV claim guidance

Safe claim after this policy and successful workflow runs:

> Designed and documented GitHub branch protection and required CI checks for a multi-workflow DevSecOps pipeline.

Stronger claim only after GitHub settings screenshot exists:

> Implemented branch protection on `main` with a stable, always-running required GitHub Actions gate that dispatches full path-aware checks for API, frontend, Docker Compose, data, Terraform, Kubernetes and security changes.
