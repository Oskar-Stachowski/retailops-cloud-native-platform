locals {
  project_slug = lower(replace(trimspace(var.project_name), "/[^a-zA-Z0-9-]/", "-"))
  env_slug     = lower(replace(trimspace(var.environment), "/[^a-zA-Z0-9-]/", "-"))

  default_name_prefix = "${local.project_slug}-${local.env_slug}"
  name_prefix         = var.name_prefix != null && trimspace(var.name_prefix) != "" ? var.name_prefix : local.default_name_prefix

  node_group_purpose_slug = lower(replace(trimspace(var.node_group_purpose), "/[^a-zA-Z0-9-_]/", "-"))
  raw_node_group_name     = var.node_group_name != null && trimspace(var.node_group_name) != "" ? var.node_group_name : "${local.name_prefix}-${local.node_group_purpose_slug}-ng"
  node_group_name         = lower(replace(trimspace(local.raw_node_group_name), "/[^a-zA-Z0-9-_]/", "-"))

  default_labels = {
    "retailops.io/environment"   = local.env_slug
    "retailops.io/node-pool"     = local.node_group_purpose_slug
    "retailops.io/workload"      = var.workload_class
    "retailops.io/capacity-type" = lower(var.capacity_type)
  }

  node_labels = merge(
    local.default_labels,
    var.labels,
  )

  common_tags = merge(
    {
      Name             = local.node_group_name
      Project          = var.project_name
      Environment      = var.environment
      ManagedBy        = "terraform"
      Component        = "eks-node-group"
      Workload         = var.workload_class
      NodeGroupPurpose = var.node_group_purpose
      Module           = "infra/modules/node_group"
      CostCenter       = "portfolio"
      Lifecycle        = var.resource_lifecycle
    },
    var.tags,
  )
}

resource "aws_eks_node_group" "this" {
  cluster_name    = var.cluster_name
  node_group_name = local.node_group_name
  node_role_arn   = var.node_role_arn
  subnet_ids      = var.subnet_ids

  ami_type             = var.ami_type
  capacity_type        = var.capacity_type
  disk_size            = var.disk_size
  force_update_version = var.force_update_version
  instance_types       = var.instance_types
  labels               = local.node_labels
  release_version      = var.release_version
  version              = var.kubernetes_version

  scaling_config {
    desired_size = var.desired_size
    max_size     = var.max_size
    min_size     = var.min_size
  }

  update_config {
    max_unavailable            = var.update_max_unavailable_percentage == null ? var.update_max_unavailable : null
    max_unavailable_percentage = var.update_max_unavailable_percentage
  }

  dynamic "taint" {
    for_each = var.taints

    content {
      key    = taint.value.key
      value  = try(taint.value.value, null)
      effect = taint.value.effect
    }
  }

  tags = local.common_tags

  lifecycle {
    ignore_changes = [
      scaling_config[0].desired_size,
    ]

    precondition {
      condition     = length(local.node_group_name) <= 63
      error_message = "EKS node group name must be 63 characters or shorter. Override node_group_name or shorten name_prefix."
    }

    precondition {
      condition     = var.min_size <= var.desired_size && var.desired_size <= var.max_size
      error_message = "Node group scaling must satisfy min_size <= desired_size <= max_size."
    }

    precondition {
      condition     = var.capacity_type != "SPOT" || length(var.instance_types) >= 2
      error_message = "SPOT node groups should use at least two similar instance types to improve capacity availability."
    }
  }
}
