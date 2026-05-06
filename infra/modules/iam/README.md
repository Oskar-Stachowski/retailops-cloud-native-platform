# IAM Module

This module defines the first controlled IAM baseline for the RetailOps Terraform/AWS foundation.

## Scope

The module creates a read-only Terraform plan policy intended for future CI/CD validation. It prepares optional role patterns for GitHub Actions and Jenkins, but those roles are disabled by default until the required trust inputs are known.

## Current behavior

By default, the module creates:

- `aws_iam_policy.terraform_plan` — read-only policy for Terraform plan and discovery operations.

By default, the module does not create:

- IAM users,
- access keys,
- `AdministratorAccess` attachments,
- write/apply deployment roles,
- workload roles for EKS or applications.

## Optional future roles

The module includes guarded support for future plan-only roles:

- GitHub Actions OIDC plan role,
- Jenkins plan role trusted by explicit AWS principal ARNs.

These roles require explicit variables and are disabled by default.

## Least-privilege note

Some AWS read/list/describe actions used by Terraform plan require `Resource = "*"`. This is acceptable here because the policy is read-only and does not include create, update, delete, pass-role, or administrator permissions.

## Future scope

Future IAM maturity may add:

- deployment roles separated from plan roles,
- ECR publisher role,
- EKS workload identity assumptions,
- permissions boundaries,
- policy-as-code checks,
- environment-specific trust policies.
