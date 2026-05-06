# Terraform Modules

This directory contains reusable Terraform modules for the RetailOps Platform.

Current modules:

- `tags` — shared governance module for standard name prefixes and mandatory AWS tags.
- `vpc` — baseline AWS networking module for the future dev environment.

Planned future module areas may include:

- IAM,
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
