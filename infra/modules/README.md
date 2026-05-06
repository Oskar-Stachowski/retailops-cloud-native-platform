# Terraform Modules

This directory contains reusable Terraform modules for the RetailOps Platform.

The project introduces modules gradually and only when the scope, cost impact, security assumptions, and validation path are clear.

Implemented modules:

- `tags` — shared governance module for standard name prefixes and mandatory AWS tags.

Planned future module areas may include:

- networking,
- IAM,
- ECR,
- RDS,
- EKS,
- observability,
- security controls.

Current module policy:

- modules should be small and reusable,
- modules should expose clear inputs and outputs,
- modules should avoid creating AWS resources before the corresponding commit explicitly introduces them,
- modules should support local validation with `terraform init -backend=false` and `terraform validate`.
