# RetailOps Terraform EKS Module

**Scope:** Control-plane module; not wired into `infra/environments/dev`.
The [node-group](node_group.md) and [OIDC](iam_oidc.md) modules are separate.

## Purpose

This module introduces the first reusable Terraform module for Amazon EKS in the RetailOps platform.

The environment supplies IAM roles, networking and access paths before deployment.

The module contract covers:

- inputs,
- outputs,
- naming,
- tags,
- provider/version constraints,
- safe EKS control plane defaults,
- OIDC issuer outputs for a separate IRSA provider,
- control-plane resources only.

## What this module creates

When used by an environment and applied intentionally, this module can create:

- one `aws_eks_cluster`,
- one customer managed KMS key for Kubernetes secrets encryption by default,
- one KMS alias for the EKS secrets key,
- one CloudWatch log group for EKS control plane logs with explicit retention and KMS encryption by default.

The module-managed KMS key has an explicit policy. Account IAM administration
is delegated through the account root principal, while CloudWatch Logs use is
limited to the cluster log group encryption context and caller account.

## Outside this module

The caller or other modules provide:

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

These are environment integration responsibilities.

## Design decisions

| Area | Decision |
|---|---|
| Module scope | EKS control plane only; node groups have a separate module. |
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
| Node groups | Provided by the separate `node_group` module. |

## Example environment wiring

The caller must define the variables below and provide an EKS cluster role.
The current `iam` module has no cluster-role output. Select the Kubernetes
version against AWS support at activation time.

```hcl
module "eks" {
  source = "../../modules/eks"

  project_name     = "retailops"
  environment      = "dev"
  cluster_role_arn = var.eks_cluster_role_arn
  subnet_ids       = module.vpc.private_subnet_ids

  kubernetes_version = var.eks_kubernetes_version

  # Private endpoint is the default. Temporarily set endpoint_public_access=true
  # and public_access_cidrs=["YOUR_PUBLIC_IP/32"] only for controlled validation.
  endpoint_public_access = false

  create_cluster_secrets_kms_key = true

  tags = module.tags.common_tags
}
```

## Validation commands

Run from the repository root:

```bash
terraform fmt -recursive infra/modules/eks
terraform -chdir=infra/modules/eks init -backend=false
terraform -chdir=infra/modules/eks validate
```

Integration, connectivity, capacity, state and cleanup must follow the
[AWS activation plan](../../plans/aws-activation.md). Static module validation
does not verify access to a private cluster endpoint or worker-node connectivity.
