locals {
  project_slug = lower(replace(trimspace(var.project_name), "/[^a-zA-Z0-9-]/", "-"))
  env_slug     = lower(replace(trimspace(var.environment), "/[^a-zA-Z0-9-]/", "-"))

  default_name_prefix = "${local.project_slug}-${local.env_slug}"
  name_prefix         = var.name_prefix != null && trimspace(var.name_prefix) != "" ? var.name_prefix : local.default_name_prefix

  oidc_provider_url       = trimspace(var.cluster_oidc_issuer_url)
  oidc_provider_host_path = trimprefix(local.oidc_provider_url, "https://")

  default_tags = {
    Name        = "${local.name_prefix}-eks-oidc-provider"
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
    Component   = "iam-oidc"
    Workload    = "platform"
    Module      = "infra/modules/iam_oidc"
    CostCenter  = "portfolio"
    Lifecycle   = var.resource_lifecycle
  }

  cluster_tags = var.cluster_name == null || trimspace(var.cluster_name) == "" ? {} : {
    ClusterName = var.cluster_name
  }

  common_tags = merge(
    local.default_tags,
    local.cluster_tags,
    var.tags,
  )

  service_account_subjects = distinct([
    for service_account in var.irsa_service_accounts :
    "system:serviceaccount:${service_account.namespace}:${service_account.name}"
  ])

  irsa_condition_keys = {
    audience = "${local.oidc_provider_host_path}:aud"
    subject  = "${local.oidc_provider_host_path}:sub"
  }
}

resource "aws_iam_openid_connect_provider" "this" {
  url             = local.oidc_provider_url
  client_id_list  = var.client_id_list
  thumbprint_list = var.thumbprint_list

  tags = local.common_tags

  lifecycle {
    precondition {
      condition     = contains(var.client_id_list, "sts.amazonaws.com")
      error_message = "client_id_list must include sts.amazonaws.com for EKS IRSA workloads."
    }
  }
}

data "aws_iam_policy_document" "irsa_assume_role" {
  count = length(local.service_account_subjects) > 0 ? 1 : 0

  statement {
    sid     = "AllowEksServiceAccountsToAssumeRole"
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.this.arn]
    }

    condition {
      test     = "StringEquals"
      variable = local.irsa_condition_keys.audience
      values   = var.client_id_list
    }

    condition {
      test     = "StringEquals"
      variable = local.irsa_condition_keys.subject
      values   = local.service_account_subjects
    }
  }
}
