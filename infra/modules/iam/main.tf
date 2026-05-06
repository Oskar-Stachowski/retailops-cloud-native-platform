locals {
  terraform_plan_policy_name = "${var.name_prefix}-iam-terraform-plan-policy"
  github_actions_role_name   = "${var.name_prefix}-iam-github-actions-plan-role"
  jenkins_role_name          = "${var.name_prefix}-iam-jenkins-plan-role"

  github_oidc_condition_prefix = replace(var.github_oidc_provider_url, "https://", "")

  github_actions_role_enabled = (
    var.enable_github_actions_plan_role &&
    var.github_oidc_provider_arn != null &&
    var.github_repository != null
  )

  jenkins_role_enabled = (
    var.enable_jenkins_plan_role &&
    length(var.jenkins_trusted_role_arns) > 0
  )
}

data "aws_iam_policy_document" "terraform_plan" {
  statement {
    sid    = "AllowTerraformPlanReadOnlyDiscovery"
    effect = "Allow"

    actions = [
      "autoscaling:Describe*",
      "cloudwatch:Describe*",
      "cloudwatch:Get*",
      "cloudwatch:List*",
      "ec2:Describe*",
      "ecr:Describe*",
      "ecr:GetAuthorizationToken",
      "ecr:ListImages",
      "eks:Describe*",
      "eks:List*",
      "elasticloadbalancing:Describe*",
      "iam:Get*",
      "iam:List*",
      "logs:Describe*",
      "rds:Describe*",
      "rds:ListTagsForResource",
      "s3:GetBucketLocation",
      "s3:ListAllMyBuckets",
      "s3:ListBucket",
      "sts:GetCallerIdentity",
      "tag:GetResources",
      "tag:GetTagKeys",
      "tag:GetTagValues"
    ]

    # Many AWS read/list/describe actions used by Terraform plan do not support
    # resource-level scoping. The policy is intentionally read-only and does not
    # grant create, update, delete, pass-role, or administrator permissions.
    resources = ["*"]
  }
}

resource "aws_iam_policy" "terraform_plan" {
  name        = local.terraform_plan_policy_name
  description = "Read-only IAM policy for future Terraform plan validation in CI/CD. No apply permissions."
  policy      = data.aws_iam_policy_document.terraform_plan.json

  tags = merge(var.common_tags, {
    Name = local.terraform_plan_policy_name
  })
}

data "aws_iam_policy_document" "github_actions_assume_role" {
  count = local.github_actions_role_enabled ? 1 : 0

  statement {
    sid     = "AllowGitHubActionsOidcAssumeRole"
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [var.github_oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.github_oidc_condition_prefix}:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringLike"
      variable = "${local.github_oidc_condition_prefix}:sub"
      values = [
        "repo:${var.github_repository}:ref:refs/heads/${var.github_branch}",
        "repo:${var.github_repository}:pull_request"
      ]
    }
  }
}

resource "aws_iam_role" "github_actions_plan" {
  count = local.github_actions_role_enabled ? 1 : 0

  name               = local.github_actions_role_name
  description        = "Future GitHub Actions role for Terraform plan-only validation."
  assume_role_policy = data.aws_iam_policy_document.github_actions_assume_role[0].json

  tags = merge(var.common_tags, {
    Name = local.github_actions_role_name
  })
}

resource "aws_iam_role_policy_attachment" "github_actions_plan" {
  count = local.github_actions_role_enabled ? 1 : 0

  role       = aws_iam_role.github_actions_plan[0].name
  policy_arn = aws_iam_policy.terraform_plan.arn
}

data "aws_iam_policy_document" "jenkins_assume_role" {
  count = local.jenkins_role_enabled ? 1 : 0

  statement {
    sid     = "AllowJenkinsAssumeRole"
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "AWS"
      identifiers = var.jenkins_trusted_role_arns
    }
  }
}

resource "aws_iam_role" "jenkins_plan" {
  count = local.jenkins_role_enabled ? 1 : 0

  name               = local.jenkins_role_name
  description        = "Future Jenkins role for Terraform plan-only validation."
  assume_role_policy = data.aws_iam_policy_document.jenkins_assume_role[0].json

  tags = merge(var.common_tags, {
    Name = local.jenkins_role_name
  })
}

resource "aws_iam_role_policy_attachment" "jenkins_plan" {
  count = local.jenkins_role_enabled ? 1 : 0

  role       = aws_iam_role.jenkins_plan[0].name
  policy_arn = aws_iam_policy.terraform_plan.arn
}
