# ADR-013: IAM delivery access model

**Status:** Accepted  
**Date:** Sprint 10  
**Scope:** IAM / CI/CD trust boundaries / Terraform plan access

---

## Context

RetailOps will eventually need CI/CD systems to interact with AWS. GitHub Actions should support code and infrastructure validation, while Jenkins may later own release-confidence workflows.

Access to AWS must be designed before automated deployment exists. The project should avoid long-lived credentials, AdministratorAccess, broad wildcard write permissions, and unclear ownership of plan versus apply actions.

Related technical documentation:

- `docs/iam-baseline.md`
- `docs/diagrams/iam-trust-boundaries.mmd`
- `docs/diagrams/07-security-and-governance-controls.md`
- `docs/ADR/CICD tooling.md`
- `infra/modules/iam/README.md`

---

## Decision

Use a least-privilege IAM baseline focused on Terraform plan and read-only discovery.

The current baseline may define future roles and policies for:

- GitHub Actions Terraform plan access,
- Jenkins release or plan access,
- short-lived role assumption patterns,
- explicit trust boundaries,
- no AdministratorAccess attachment,
- no application business-data access as a side effect of infrastructure access.

Terraform apply, deployment permissions, and production access are out of scope for this ADR and require later approval decisions.

---

## Options considered

### Option 1 — Use local AWS credentials only

Keep all AWS access manual from a developer machine.

This is simple for early learning, but it does not prepare the project for CI/CD maturity or auditable delivery.

### Option 2 — Define plan-oriented IAM baseline now

Create a controlled baseline for future CI/CD AWS access, focused on read-only discovery and explicit trust boundaries.

This supports Terraform validation and governance without granting deployment power too early.

### Option 3 — Give CI/CD broad deploy permissions immediately

Allow CI/CD to create and update all infrastructure from the beginning.

This is convenient, but it violates least privilege and makes accidental AWS changes more likely.

---

## Decision outcome

Choose **Option 2: plan-oriented IAM baseline now**.

The delivery systems should first prove that they can validate and review infrastructure safely. Deployment permissions come later.

---

## Consequences

Positive consequences:

- IAM intent is visible before CI/CD deployment is automated.
- GitHub Actions and Jenkins have clear future trust boundaries.
- Terraform plan can be separated from Terraform apply.
- The project avoids AdministratorAccess and long-lived secrets as default patterns.

Trade-offs:

- Some read/list/describe AWS permissions may still require broad resource scope because AWS does not support resource-level scoping for every discovery action.
- Checkov may report policy-resource findings that need documented exceptions or future refinement.
- Real OIDC trust must be finalized with actual repository and account identifiers before real AWS use.

---

## Follow-up decisions

Future ADRs should decide:

- GitHub Actions OIDC provider setup,
- Jenkins credential and role-assumption strategy,
- separate apply role permissions,
- manual approval gates for Terraform apply,
- how IAM policy exceptions are documented and reviewed.
