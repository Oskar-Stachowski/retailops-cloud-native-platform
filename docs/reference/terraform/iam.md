# IAM Module

This module defines the first controlled IAM baseline for the RetailOps Terraform/AWS foundation.

## Scope

The module defines a read-only Terraform plan policy and optional GitHub Actions
and Jenkins plan roles. Both role flags are disabled in the dev example.
This is distinct from the already existing GitHub OIDC plan role recorded in
[the account evidence](../../evidence/aws/2026-09-26-state-drift.md), which was
preserved outside the empty dev state.

## Current behavior

By default, the module creates:

- `aws_iam_policy.terraform_plan` — read-only policy for Terraform plan and discovery operations.

By default, the module does not create:

- IAM users,
- access keys,
- `AdministratorAccess` attachments,
- write/apply deployment roles,
- workload roles for EKS or applications.

## Optional roles

The module supports plan-only roles with explicit trust inputs:

- GitHub Actions OIDC plan role,
- Jenkins plan role trusted by explicit AWS principal ARNs.

These roles require explicit variables and are disabled by default.

## Least-privilege note

Some AWS read/list/describe actions used by Terraform plan require `Resource = "*"`. This is acceptable here because the policy is read-only and does not include create, update, delete, pass-role, or administrator permissions.

## Deployment boundary

The module does not grant apply or publish permissions and does not create EKS
cluster/node roles. S3 state locking needs separate scoped lock-file access from
the [state backend](../terraform-state-backend.md). Role adoption, deployment
permissions and workload identity require explicit environment wiring.
