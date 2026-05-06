# Terraform Modules

This directory contains reusable Terraform modules for the RetailOps Platform.

Current modules:

- `tags` — shared naming and tagging baseline used by future AWS resources.
- `vpc` — AWS networking baseline with VPC, public/private subnet assumptions, route tables, Internet Gateway, and baseline security groups.
- `iam` — IAM baseline with a read-only Terraform plan policy and guarded future role patterns for CI/CD.

Planned future module areas may include:

- ECR,
- RDS,
- EKS,
- observability,
- security controls,
- budgets and cost monitoring.

Module implementation should remain incremental. Each module should have a clear scope, cost impact, security assumption, and validation path before it is connected to an environment.

Current module policy:

- modules should be small and reusable,
- modules should expose clear inputs and outputs,
- modules should avoid creating AWS resources before the corresponding commit explicitly introduces them,
- modules should support local validation with `terraform init -backend=false` and `terraform validate`.
