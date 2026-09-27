# RetailOps Terraform EKS Managed Node Group Module

**Scope:** Managed node-group module; not wired into `infra/environments/dev`.

## Purpose

This module introduces a reusable Terraform contract for an Amazon EKS managed node group.

The module exposes:

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
- access to required AWS APIs, DNS and image registries.

## What this module does not create

The following are outside this module:

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

They are supplied by the deployment's environment composition.

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
| Desired size drift | Terraform ignores later `desired_size` drift to allow runtime scaling; define who owns this value when deploying. |
| Apply policy | Use the [AWS activation plan](../../plans/aws-activation.md). |

## Example environment wiring

The caller must define `eks_node_role_arn`; the current `iam` module does not
create a node role. The EKS/VPC/tags modules below must also be wired by the caller.

```hcl
module "eks_node_group_general" {
  source = "../../modules/node_group"

  project_name  = "retailops"
  environment   = "dev"
  cluster_name  = module.eks.cluster_name
  node_role_arn = var.eks_node_role_arn
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

  tags = module.tags.common_tags
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
  node_role_arn = var.eks_node_role_arn
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

  tags = module.tags.common_tags
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

These defaults are configuration values, not measured sizing or a price estimate.
Size nodes from actual workload and add-on requests; verify capacity and costs
before deployment. `max_size` does not cap all costs of an EKS environment.

## Plan-first validation commands

Run from the repository root:

```bash
terraform fmt -recursive infra/modules/node_group
terraform -chdir=infra/modules/node_group init -backend=false
terraform -chdir=infra/modules/node_group validate
```

For deployment plans use the actual state and parameters, and retain only
sanitized evidence. See [infrastructure operations](../../guides/infrastructure.md).
