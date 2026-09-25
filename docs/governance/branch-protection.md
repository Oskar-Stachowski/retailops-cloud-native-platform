# GitHub Branch Protection Policy

## Purpose

This document defines the expected GitHub branch protection settings for the RetailOps repository. It is reviewer-facing evidence for the GitHub Actions CI workstream and explains which checks should block merges before code reaches `main`.

The policy is intentionally documented in the repository because GitHub branch protection itself is configured in repository settings and cannot be fully enforced by ordinary application code.

## Protected branch

Enabled and verified on 2026-09-25 through the authenticated GitHub REST
branch and branch-protection endpoints. `main` reports `protected: true`.
The [captured settings and verification notes](../evidence/github/README.md)
record the active configuration below.

| Setting | Active value |
|---|---|
| Protected branch pattern | `main` |
| Merge model | Pull request before merge |
| Direct pushes to `main` | Changes must go through a pull request, including for administrators |
| Force pushes | Disabled |
| Branch deletion | Disabled |
| Required approvals | 0 for the current solo-maintainer workflow; a pull request is still required |
| Stale approvals | Dismiss stale approvals when new commits are pushed |
| Conversation resolution | Required before merge |
| Administrator enforcement | Enabled; no PR bypass allowances |
| Up-to-date PR branch | Required before merge |

Code-owner review and last-push approval are disabled for the solo-maintainer
workflow. Enable at least one required approval when a separate reviewer is
available; the author cannot approve their own pull request.

## Required status checks

Only this stable aggregate check is configured as required:

| Workflow | Required check / job | Why it matters |
|---|---|---|
| Required CI | `required-result` from GitHub Actions (app ID `15368`) | Always runs for every PR, every push to `main`, and manual dispatch. It calls the existing full domain workflows selected by tested path detection and fails if a required workflow is skipped, cancelled or unsuccessful. |

The workflow/job label is `Required CI / required-result`, but the exact API
check context is `required-result`. Requiring the combined display label
would wait for a different check name. The expected provider is explicitly
bound to the GitHub Actions app.

Do not configure domain workflows as separate required branch protection checks. `Required CI` is the only automatic pull-request and `main` push orchestrator; it invokes the full domain workflows through `workflow_call`. Domain workflows remain manually dispatchable for standalone evidence without duplicating or cancelling Required CI jobs. The stable `required-result` job verifies the expected-versus-actual result of every called workflow.

Optional checks, depending on current sprint scope:

| Workflow | Check | When to require |
|---|---|---|
| API CI | `API integration tests`, `API Docker image build` | Called by Required CI for API/data/shared/unknown changes. |
| Frontend CI | `Frontend tests and lint`, `Build frontend application`, `Build frontend Docker image` | Called by Required CI for frontend/shared/unknown changes. |
| Docker Compose CI | `Validate Docker Compose config`, `Build full stack and run smoke tests` | Called by Required CI for application, data, Compose, shared and unknown changes. |
| Security CI | Security scan jobs and `Security evidence summary` | Called with explicit blocking thresholds for application, Compose, Kubernetes, policy, security, shared and unknown changes. |
| Data CI | `Synthetic data quality gate` | Called by Required CI for data/shared/unknown changes. |
| Terraform Validation CI | `Terraform fmt, init and validate` | Called by Required CI for Terraform/shared/unknown changes. It has read-only repository permissions and no AWS credentials. |
| IaC Security CI | `TFLint IaC quality gate`, `Checkov IaC security report` | Called by Required CI together with Terraform validation; Checkov is blocking outside documented exceptions. |
| Kubernetes Policy CI | `Kustomize, schema and policy gates` | Called for Kubernetes/policy/shared/unknown changes; runs Kustomize, Kubeconform, Conftest and Checkov. |
| Observability CI | `Validate observability assets` | Require once observability assets are in active scope |
| Provenance CI | `Build local images and generate provenance attestations` | Require for release branches or signed release candidate evidence, not necessarily every PR |
| Terraform Dev Plan | `Optional dev Terraform plan` | Manual-only; never require on normal PRs. Run only after explicit dispatch confirmation and configuration of the plan-only AWS OIDC role. |

## Evidence collection

For every CI-related portfolio claim, collect at least one of the following:

- screenshot of a green workflow run;
- link to a successful GitHub Actions run;
- downloaded artifact from `ci-cd/reports/**`;
- screenshot of branch protection settings showing required checks;
- authenticated API snapshot of branch-protection settings and its capture date;
- short note in `docs/evidence/index.md` describing what changed and when evidence was refreshed.

## Reviewer checklist

Configuration verified on 2026-09-25:

- [x] `main` is protected in GitHub repository settings.
- [x] Pull requests are required before merging.
- [x] Direct pushes, force pushes and branch deletion are disallowed by the active configuration, including for administrators.
- [x] The only required check context is `required-result` from GitHub Actions.
- [x] At least one green `Required CI / required-result` run exists.
- [x] An API snapshot and reviewer-visible note are stored under `docs/evidence/github/` and referenced in the evidence ledger.

These checks record live configuration inspection. No destructive push or
branch-deletion attempt was made against `main`.

## CV claim guidance

Safe claim after this policy and successful workflow runs:

> Designed and documented GitHub branch protection and required CI checks for a multi-workflow DevSecOps pipeline.

Claim supported by the captured GitHub settings:

> Implemented branch protection on `main` with a stable, always-running required GitHub Actions gate that dispatches full path-aware checks for API, frontend, Docker Compose, data, Terraform, Kubernetes and security changes.
