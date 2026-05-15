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
| Required CI | `Required CI / required-result` | Always runs for every PR, every push to `main`, and manual dispatch. It performs path-aware lightweight gates and fails when any required gate fails. |

Do not configure the path-filtered domain workflows as required branch protection checks. They remain useful as deeper CI and evidence workflows, but they intentionally use `pull_request.paths` filters and are not guaranteed to run for every PR.

Optional checks, depending on current sprint scope:

| Workflow | Check | When to require |
|---|---|---|
| API CI | `API integration tests`, `API Docker image build` | Optional deep backend evidence; do not mark as branch-protection required while workflow-level path filters remain in use. |
| Frontend CI | `Frontend tests and lint`, `Build frontend application`, `Build frontend Docker image` | Optional deep frontend evidence; do not mark as branch-protection required while workflow-level path filters remain in use. |
| Docker Compose CI | `Validate Docker Compose config`, `Build full stack and run smoke tests` | Optional runtime evidence; do not mark as branch-protection required while workflow-level path filters remain in use. |
| Security CI | Security scan jobs and `Security evidence summary` | Optional DevSecOps evidence; do not use the summary job as the only branch-protection gate. |
| Data CI | `Synthetic data quality gate` | Optional data evidence; do not mark as branch-protection required while workflow-level path filters remain in use. |
| Terraform IaC CI | `Terraform fmt, init and validate` | Optional IaC evidence; do not mark as branch-protection required while workflow-level path filters remain in use. |
| IaC Security CI | `TFLint IaC quality gate`, `Checkov IaC security report` | Optional IaC security evidence; do not mark as branch-protection required while workflow-level path filters remain in use. |
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

> Implemented branch protection on `main` with a stable, always-running required GitHub Actions gate that dispatches path-aware checks for API, frontend, Docker Compose, data, and IaC changes.
