# RetailOps Terraform EKS Managed Node Group Module

**Commit:** 13.3 — `terraform: add EKS node group module`

**Sprint:** 13 — Kubernetes / EKS Foundation

**Status:** Module skeleton, plan-first, no environment wiring required in this commit.

## Purpose

This module introduces a reusable Terraform contract for an Amazon EKS managed node group.

Commit 13.3 is intentionally focused on worker-node capacity assumptions before real cluster creation:

- instance types,
- desired/min/max capacity,
- node labels,
- optional taints,
- tags,
- safe naming,
- cost-aware defaults,
- plan evidence without `terraform apply`.

## What this module creates

When used by an environment and applied intentionally, this module can create:

- one `aws_eks_node_group` attached to an existing EKS cluster.

The module expects that the following already exist or are provided by other modules:

- EKS cluster,
- node IAM role,
- VPC subnets,
- security/networking design,
- future OIDC/IRSA foundation.

## What this module does not create

The following items are intentionally out of scope for Commit 13.3:

- EKS cluster control plane,
- IAM roles or IAM policy attachments,
- launch templates,
- remote SSH access,
- Cluster Autoscaler,
- Karpenter,
- Kubernetes namespaces,
- workload manifests,
- ingress or load balancers,
- observability agents,
- production autoscaling policies.

Those belong to later commits or later sprints.

## Design decisions

| Area | Decision |
|---|---|
| Node type | EKS managed node group, not self-managed EC2 nodes. |
| Module boundary | Node group only; IAM and networking are injected from environment/modules. |
| Default capacity | `min_size = 0`, `desired_size = 1`, `max_size = 2` for dev validation. |
| Default instance type | `t3.small` to keep dev cost low. Increase to `t3.medium` or larger if pods are resource-constrained. |
| Capacity type | `ON_DEMAND` by default for stable platform workloads. |
| Spot usage | Allowed, but requires at least two similar instance types. |
| Labels | Default RetailOps labels are applied and can be extended or overridden. |
| Taints | Supported for dedicated node groups such as observability, ML, batch, or spot. |
| SSH access | Not configured. Debug through Kubernetes/SSM-oriented practices later, not open SSH by default. |
| Desired size drift | Terraform ignores later `desired_size` drift so a future autoscaler does not fight Terraform. |
| Apply policy | Do not apply in Commit 13.3 unless a dedicated EKS validation window is planned. |

## Example usage for a later environment commit

```hcl
module "eks_node_group_general" {
  source = "../../modules/node_group"

  project_name  = "retailops"
  environment   = "dev"
  cluster_name  = module.eks.cluster_name
  node_role_arn = module.iam.eks_node_role_arn
  subnet_ids    = module.vpc.private_subnet_ids

  node_group_purpose = "general"
  workload_class     = "application"

  capacity_type  = "ON_DEMAND"
  instance_types = ["t3.small"]

  min_size     = 0
  desired_size = 1
  max_size     = 2

  labels = {
    "retailops.io/tier" = "application"
  }

  tags = local.common_tags
}
```

## Optional Spot example

Use Spot only for interruption-tolerant workloads, not for first platform-critical workloads.

```hcl
module "eks_node_group_spot" {
  source = "../../modules/node_group"

  project_name  = "retailops"
  environment   = "dev"
  cluster_name  = module.eks.cluster_name
  node_role_arn = module.iam.eks_node_role_arn
  subnet_ids    = module.vpc.private_subnet_ids

  node_group_purpose = "spot"
  workload_class     = "batch"

  capacity_type = "SPOT"
  instance_types = [
    "t3.small",
    "t3a.small",
  ]

  min_size     = 0
  desired_size = 0
  max_size     = 2

  taints = [
    {
      key    = "retailops.io/capacity"
      value  = "spot"
      effect = "NO_SCHEDULE"
    }
  ]

  labels = {
    "retailops.io/interruption-tolerant" = "true"
  }

  tags = local.common_tags
}
```

## Capacity assumptions

For the RetailOps portfolio project, this module starts with small, explicit capacity:

| Assumption | Default | Reason |
|---|---:|---|
| Minimum nodes | `0` | Allows cost-aware scale-down in dev-style environments. |
| Desired nodes | `1` | Enough for a small validation cluster, but not production HA. |
| Maximum nodes | `2` | Limits accidental EC2 cost during early validation. |
| Instance type | `t3.small` | Low-cost baseline for plan/demo; may be too small for heavier add-ons. |
| Disk size | `20 GiB` | Minimal Linux node root volume baseline. |
| Capacity type | `ON_DEMAND` | More predictable than Spot for core validation. |

Senior note: if you later install many platform add-ons, `t3.small` may be too small. For a more comfortable demo cluster, consider `t3.medium`, but update the cost review first.

## Plan-first validation commands

Run from the repository root:

```bash
terraform fmt -recursive infra/modules/node_group
terraform -chdir=infra/modules/node_group init -backend=false
terraform -chdir=infra/modules/node_group validate
```

Recommended evidence capture:

```bash
mkdir -p ci-cd/reports/iac
terraform -chdir=infra/modules/node_group validate \
  | tee ci-cd/reports/iac/terraform-validate-eks-node-group-module.txt
```

When the module is later wired into `infra/environments/dev`, generate a plan only:

```bash
terraform -chdir=infra/environments/dev plan \
  -out=tfplan-eks-node-group

terraform -chdir=infra/environments/dev show -no-color tfplan-eks-node-group \
  | tee ci-cd/reports/iac/terraform-plan-eks-node-group.txt
```

Do not run `terraform apply` as part of Commit 13.3.

## Senior review checklist

Before moving to Commit 13.4 or 13.5, verify:

- the module creates only `aws_eks_node_group`,
- no real AWS resources were applied during this commit,
- node IAM role ARN is injected, not hardcoded,
- cluster name is injected, not discovered implicitly,
- subnet IDs are injected, not discovered implicitly,
- default capacity is intentionally small,
- Spot node groups require multiple instance types,
- labels clearly describe environment, node pool, workload, and capacity type,
- taints are optional and use valid EKS/Terraform effects,
- tags include cost and lifecycle context,
- `terraform fmt` and `terraform validate` pass locally.
