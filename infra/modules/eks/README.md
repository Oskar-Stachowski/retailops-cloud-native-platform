# RetailOps Terraform EKS Module

**Commit:** 13.2 — `terraform: add EKS module skeleton`

**Sprint:** 13 — Kubernetes / EKS Foundation

**Status:** Module skeleton, plan-first, no managed node group yet.

## Purpose

This module introduces the first reusable Terraform module for Amazon EKS in the RetailOps platform.

The goal of this commit is to define the EKS cluster contract before wiring it into `infra/environments/dev`.

This commit intentionally focuses on:

- inputs,
- outputs,
- naming,
- tags,
- provider/version constraints,
- safe EKS control plane defaults,
- future OIDC/IRSA readiness,
- no full node group implementation yet.

## What this module creates

When used by an environment and applied intentionally, this module can create:

- one `aws_eks_cluster`,
- one customer managed KMS key for Kubernetes secrets encryption by default,
- one KMS alias for the EKS secrets key,
- one CloudWatch log group for EKS control plane logs with explicit retention and KMS encryption by default.

## What this module does not create yet

The following items are intentionally out of scope for Commit 13.2:

- EKS managed node groups,
- self-managed node groups,
- Fargate profiles,
- IAM roles for cluster or workloads,
- OIDC provider resource,
- IRSA service accounts,
- Kubernetes namespaces,
- workload manifests,
- ingress controller,
- load balancers,
- autoscaling policies,
- production observability agents.

Those belong to later Sprint 13 commits.

## Design decisions

| Area | Decision |
|---|---|
| Module scope | EKS control plane only; no node group yet. |
| IAM role | Passed as `cluster_role_arn` from an IAM/environment layer. |
| Subnets | Passed as `subnet_ids`; the environment decides public/private subnet strategy. |
| Public API endpoint | Disabled by default; the module is private-endpoint-first to satisfy the EKS public endpoint Checkov gate. |
| Public endpoint wide-open access | Blocked by validation for `0.0.0.0/0` when a temporary public endpoint is intentionally enabled. |
| Kubernetes secrets encryption | Enabled by default with a customer managed KMS key, or an existing KMS key ARN can be injected. |
| Control plane logs | API, audit, and authenticator logs are enabled by default for baseline visibility. |
| Log retention | Required when control plane logs are enabled and defaults to a short dev-friendly retention period. |
| Log encryption | EKS control plane logs use the same customer managed KMS key unless a dedicated CloudWatch KMS key is injected. |
| Kubernetes version | Pinned as an explicit input with a safe default; verify standard support before apply. |
| Upgrade support | Defaults to `STANDARD` to avoid extended-support cost posture. |
| Access mode | Defaults to `API_AND_CONFIG_MAP` for compatibility during transition to EKS access entries. |
| Node groups | Not implemented in this commit. |

## Example usage for a later environment commit

Do not wire this into `infra/environments/dev` in Commit 13.2 unless that is your explicit task.

```hcl
module "eks" {
  source = "../../modules/eks"

  project_name     = "retailops"
  environment      = "dev"
  cluster_role_arn = module.iam.eks_cluster_role_arn
  subnet_ids       = module.vpc.private_subnet_ids

  kubernetes_version = "1.33"

  # Private endpoint is the default. Temporarily set endpoint_public_access=true
  # and public_access_cidrs=["YOUR_PUBLIC_IP/32"] only for controlled validation.
  endpoint_public_access = false

  create_cluster_secrets_kms_key = true

  tags = local.common_tags
}
```

## Validation commands

Run from the repository root:

```bash
terraform fmt -recursive infra/modules/eks
terraform -chdir=infra/modules/eks init -backend=false
terraform -chdir=infra/modules/eks validate
```

Recommended evidence capture:

```bash
mkdir -p ci-cd/reports/iac
terraform -chdir=infra/modules/eks validate | tee ci-cd/reports/iac/terraform-validate-eks-module.txt
```

## Apply policy

Do not run `terraform apply` for EKS during this commit.

Commit 13.2 is a module-contract commit. A real EKS cluster should only be created during a dedicated validation window after cost, cleanup, IAM, networking, and access assumptions are reviewed.

Expected safe workflow:

```text
write module → fmt → init -backend=false → validate → review → commit
```

Not yet:

```text
apply → create cluster → create node group → deploy workloads
```

## Senior review checklist

Before moving to Commit 13.3 or 13.5, verify:

- the module has no node group resources,
- the cluster role is injected instead of hardcoded,
- subnet IDs are injected instead of discovered implicitly,
- public API access is disabled by default and never open to `0.0.0.0/0`,
- Kubernetes secrets encryption is configured with a customer managed KMS key,
- EKS control plane logs have explicit retention and KMS encryption,
- tags include project, environment, owner/cost context from the environment layer,
- OIDC issuer output is available for future IRSA work,
- outputs are useful but do not expose secrets,
- `terraform fmt` and `terraform validate` pass locally.
