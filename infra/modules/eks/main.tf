locals {
  project_slug = lower(replace(trimspace(var.project_name), "/[^a-zA-Z0-9-]/", "-"))
  env_slug     = lower(replace(trimspace(var.environment), "/[^a-zA-Z0-9-]/", "-"))

  default_name_prefix = "${local.project_slug}-${local.env_slug}"
  name_prefix         = var.name_prefix != null && trimspace(var.name_prefix) != "" ? var.name_prefix : local.default_name_prefix
  cluster_name        = var.cluster_name != null && trimspace(var.cluster_name) != "" ? var.cluster_name : "${local.name_prefix}-eks"

  cluster_secrets_kms_key_arn = var.cluster_secrets_kms_key_arn != null ? var.cluster_secrets_kms_key_arn : aws_kms_key.cluster_secrets[0].arn
  cloudwatch_kms_key_id       = var.cloudwatch_log_group_kms_key_id != null ? var.cloudwatch_log_group_kms_key_id : local.cluster_secrets_kms_key_arn

  common_tags = merge(
    {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
      Component   = "eks"
      Workload    = "platform"
      Module      = "infra/modules/eks"
      CostCenter  = "portfolio"
      Lifecycle   = var.resource_lifecycle
    },
    var.tags,
  )
}

resource "aws_kms_key" "cluster_secrets" {
  count = var.create_cluster_secrets_kms_key ? 1 : 0

  description             = "KMS key for ${local.cluster_name} Kubernetes secrets encryption and EKS control plane logs"
  deletion_window_in_days = var.kms_key_deletion_window_in_days
  enable_key_rotation     = true

  tags = merge(
    local.common_tags,
    {
      Name = "${local.cluster_name}-secrets"
    },
  )
}

resource "aws_kms_alias" "cluster_secrets" {
  count = var.create_cluster_secrets_kms_key ? 1 : 0

  name          = "alias/${local.cluster_name}-secrets"
  target_key_id = aws_kms_key.cluster_secrets[0].key_id
}

resource "aws_cloudwatch_log_group" "cluster" {
  count = var.create_cloudwatch_log_group ? 1 : 0

  name              = "/aws/eks/${local.cluster_name}/cluster"
  retention_in_days = var.cloudwatch_log_retention_in_days
  kms_key_id        = local.cloudwatch_kms_key_id
  tags              = local.common_tags
}

resource "aws_eks_cluster" "this" {
  name     = local.cluster_name
  role_arn = var.cluster_role_arn
  version  = var.kubernetes_version

  enabled_cluster_log_types = var.enabled_cluster_log_types

  access_config {
    authentication_mode                         = var.authentication_mode
    bootstrap_cluster_creator_admin_permissions = var.bootstrap_cluster_creator_admin_permissions
  }

  encryption_config {
    provider {
      key_arn = local.cluster_secrets_kms_key_arn
    }

    resources = ["secrets"]
  }

  kubernetes_network_config {
    ip_family         = var.ip_family
    service_ipv4_cidr = var.ip_family == "ipv4" ? var.service_ipv4_cidr : null
  }

  upgrade_policy {
    support_type = var.upgrade_support_type
  }

  vpc_config {
    subnet_ids              = var.subnet_ids
    security_group_ids      = var.cluster_security_group_ids
    endpoint_private_access = var.endpoint_private_access
    endpoint_public_access  = var.endpoint_public_access
    public_access_cidrs     = var.endpoint_public_access ? var.public_access_cidrs : null
  }

  tags = local.common_tags

  depends_on = [
    aws_cloudwatch_log_group.cluster,
  ]

  lifecycle {
    precondition {
      condition     = length(var.enabled_cluster_log_types) == 0 || var.create_cloudwatch_log_group
      error_message = "Set create_cloudwatch_log_group=true when EKS control plane logs are enabled so log retention is explicitly controlled."
    }

    precondition {
      condition     = !var.endpoint_public_access || length(var.public_access_cidrs) > 0
      error_message = "Set at least one trusted public_access_cidrs entry when endpoint_public_access=true, or keep the EKS endpoint private-only."
    }
  }
}
