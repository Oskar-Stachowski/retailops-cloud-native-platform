## Accepted IAM Exception: Terraform Plan Read-Only Discovery

The Terraform plan IAM policy intentionally allows broad read-only discovery actions
such as Describe, List, and Get across selected AWS services.

## Reason:
Terraform plan requires read-only visibility into existing AWS resources in order to
compare desired infrastructure state with the current AWS account state. Many AWS
Describe/List actions do not support resource-level scoping.

## Risk:
Low. The policy does not grant create, update, delete, iam:PassRole, or administrator
permissions.

## Controls:
- Policy is intended for plan-only CI/CD validation.
- No terraform apply permissions are granted.
- Critical guardrails check for AdministratorAccess, IAM users, access keys, and
  wildcard write actions.
- Future improvement: enforce this exception through policy-as-code with explicit
  justification and review/expiry metadata.
