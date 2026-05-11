# ADR-010: Terraform layout for AWS foundation

**Status:** Accepted
**Date:** Sprint 10
**Scope:** Terraform / AWS foundation / repository structure

---

## Context

RetailOps is moving from local-first DevOps evidence toward a Terraform-managed AWS foundation.

At this stage, the project needs a layout that supports review, validation, future environments, and reusable modules, but it must not create unnecessary cloud cost or hide complexity behind premature abstraction.

The current Sprint 10 scope is intentionally limited to a `dev` environment and reusable baseline modules.

Related technical documentation:

- `infra/README.md`
- `infra/modules/README.md`
- `docs/naming-convention.md`
- `docs/tagging-strategy.md`

---

## Decision

Use a simple environment-and-module Terraform layout:

```text
infra/
├── environments/
│   └── dev/
└── modules/
    ├── tags/
    ├── vpc/
    ├── iam/
    ├── ecr/
    ├── budget/
    └── cloudwatch/
```

The `dev` environment is the first composition layer. Reusable modules live under `infra/modules/` and are wired from `infra/environments/dev/main.tf`.

Terraform should be validated locally first with:

```bash
terraform -chdir=infra/environments/dev fmt -recursive
terraform -chdir=infra/environments/dev init -backend=false
terraform -chdir=infra/environments/dev validate
```

Terraform `apply` is not part of this ADR. It requires a separate delivery and approval decision.

---

## Options considered

### Option 1 — Flat Terraform files only

Keep all Terraform code directly inside one environment folder.

This is simple at the beginning, but it becomes harder to reuse and review once networking, IAM, ECR, cost controls, and observability grow.

### Option 2 — Environment plus reusable modules

Use one environment composition layer and small modules for stable concerns.

This provides enough structure for future growth without turning the portfolio project into an over-engineered Terraform platform.

### Option 3 — Full multi-environment platform layout from day one

Create `dev`, `staging`, `prod`, remote state, workspaces, promotion pipelines, and policy-as-code immediately.

This would look enterprise-like, but it adds too much complexity before the project has real AWS deployment maturity.

---

## Decision outcome

Choose **Option 2: environment plus reusable modules**.

This gives the project a production-relevant shape while keeping Sprint 10 understandable, cost-aware, and safe to validate locally.

---

## Consequences

Positive consequences:

- Terraform code is easier to review module by module.
- Future services can reuse naming, tagging, networking, IAM, and cost patterns.
- CI can validate the environment without running `apply`.
- The repository demonstrates infrastructure design discipline.

Trade-offs:

- The root environment file can become long if too many variables are declared there.
- Module interfaces must stay clear and intentionally small.
- Future environments should be added only when there is a real delivery need.

---

## Follow-up decisions

Future ADRs should decide:

- remote state backend and locking,
- promotion strategy across environments,
- Terraform apply ownership,
- drift detection,
- policy-as-code enforcement.
