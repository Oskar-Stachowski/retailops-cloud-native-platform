# Infrastructure

This directory contains the infrastructure documentation and future
Infrastructure-as-Code entry points for the RetailOps Platform.

## Current status

There is no active Terraform root module in this branch.

Do not run `terraform init`, `terraform plan`, or `terraform apply` from the
`infra/` directory unless an environment-specific Terraform entry point has
been added first.

## Entry point convention

When Terraform is introduced, environment roots should live under:

```text
infra/environments/<environment>/
```

For example:

```text
infra/environments/dev/
```

Reusable modules should live under:

```text
infra/modules/
```

The repository root of `infra/` should remain documentation and shared context
only, unless it is intentionally converted into a reusable module and documented
as such.

## Planned responsibilities

- define Terraform-based AWS infrastructure,
- separate environments such as dev, staging, and prod,
- prepare reusable infrastructure modules,
- document cloud infrastructure assumptions,
- support future EKS, ECR, IAM, networking, storage, and monitoring setup.
