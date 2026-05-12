terraform {
  required_version = ">= 1.6.0, < 2.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.44"
    }
  }
}

variable "project_name" {
  description = "Short project name used for naming and tagging AWS resources."
  type        = string
  default     = "retailops"
}

variable "environment" {
  description = "Deployment environment name."
  type        = string
  default     = "dev"

  validation {
    condition     = var.environment == "dev"
    error_message = "This environment entry point is dev-only."
  }
}

variable "aws_region" {
  description = "AWS region selected for the future dev environment."
  type        = string
  default     = "eu-central-1"
}

variable "owner" {
  description = "Human owner used for cost and responsibility tagging."
  type        = string
  default     = "oskar-stachowski"
}

variable "cost_center" {
  description = "Cost allocation tag."
  type        = string
  default     = "portfolio"
}

variable "managed_by" {
  description = "Provisioning method tag."
  type        = string
  default     = "terraform"
}

variable "resource_lifecycle" {
  description = "Resource lifecycle intent for future cost-control decisions."
  type        = string
  default     = "temporary"
}

variable "additional_tags" {
  description = "Additional non-sensitive tags merged into common_tags."
  type        = map(string)
  default     = {}
}

variable "vpc_cidr_block" {
  description = "CIDR block for the dev VPC baseline."
  type        = string
  default     = "10.20.0.0/16"
}

variable "public_subnets" {
  description = "Public subnet definitions for the dev VPC baseline."
  type = map(object({
    cidr_block        = string
    availability_zone = string
  }))

  default = {
    a = {
      cidr_block        = "10.20.0.0/24"
      availability_zone = "eu-central-1a"
    }
    b = {
      cidr_block        = "10.20.1.0/24"
      availability_zone = "eu-central-1b"
    }
  }
}

variable "private_subnets" {
  description = "Private subnet definitions for the dev VPC baseline. No NAT Gateway is created in this sprint."
  type = map(object({
    cidr_block        = string
    availability_zone = string
  }))

  default = {
    a = {
      cidr_block        = "10.20.10.0/24"
      availability_zone = "eu-central-1a"
    }
    b = {
      cidr_block        = "10.20.11.0/24"
      availability_zone = "eu-central-1b"
    }
  }
}


variable "enable_github_actions_plan_role" {
  description = "Enable future GitHub Actions plan-only role when OIDC trust inputs are provided."
  type        = bool
  default     = false
}

variable "github_oidc_provider_arn" {
  description = "Existing AWS IAM OIDC provider ARN for GitHub Actions. Keep null until intentionally configured."
  type        = string
  default     = null
}

variable "github_repository" {
  description = "GitHub repository allowed to assume the future GitHub Actions plan role, in owner/repository format."
  type        = string
  default     = null
}

variable "github_branch" {
  description = "Branch allowed to assume the future GitHub Actions plan role."
  type        = string
  default     = "main"
}

variable "enable_jenkins_plan_role" {
  description = "Enable future Jenkins plan-only role when trusted AWS principal ARNs are provided."
  type        = bool
  default     = false
}

variable "jenkins_trusted_role_arns" {
  description = "AWS principal ARNs allowed to assume the future Jenkins plan role."
  type        = list(string)
  default     = []
}

variable "ecr_repositories" {
  description = "ECR repositories for RetailOps container images."
  type = map(object({
    repository_suffix = string
    max_image_count   = optional(number, 20)
  }))

  default = {
    api = {
      repository_suffix = "api"
    }
    frontend = {
      repository_suffix = "frontend"
    }
  }
}

variable "enable_monthly_budget" {
  description = "Enable the monthly AWS Budget guardrail for the dev environment. Keep plan-only until cost assumptions are reviewed."
  type        = bool
  default     = true
}

variable "monthly_budget_limit_usd" {
  description = "Monthly AWS Budget limit for the dev guardrail, in USD."
  type        = number
  default     = 10

  validation {
    condition     = var.monthly_budget_limit_usd > 0 && var.monthly_budget_limit_usd <= 100
    error_message = "The dev monthly budget limit should be greater than 0 and no higher than 100 USD."
  }
}

variable "enable_budget_notifications" {
  description = "Enable AWS Budget email notifications. Keep false in committed examples to avoid storing private email addresses."
  type        = bool
  default     = false
}

variable "budget_notification_email_addresses" {
  description = "Private email addresses for AWS Budget notifications. Do not commit real addresses; use local terraform.tfvars instead."
  type        = list(string)
  default     = []
  sensitive   = true
}

variable "cloudwatch_log_groups" {
  description = "CloudWatch log groups for the minimal AWS-native logging baseline."
  type = map(object({
    name_suffix       = string
    retention_in_days = optional(number, 7)
    kms_key_id        = optional(string)
    skip_destroy      = optional(bool, false)
  }))

  default = {
    api = {
      name_suffix       = "api"
      retention_in_days = 7
    }
    frontend = {
      name_suffix       = "frontend"
      retention_in_days = 7
    }
    platform = {
      name_suffix       = "platform"
      retention_in_days = 7
    }
  }
}

module "tags" {
  source = "../../modules/tags"

  project_name       = var.project_name
  environment        = var.environment
  owner              = var.owner
  managed_by         = var.managed_by
  cost_center        = var.cost_center
  resource_lifecycle = var.resource_lifecycle
  additional_tags    = var.additional_tags
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = module.tags.common_tags
  }
}

module "vpc" {
  source = "../../modules/vpc"

  name_prefix     = module.tags.name_prefix
  common_tags     = module.tags.common_tags
  vpc_cidr_block  = var.vpc_cidr_block
  public_subnets  = var.public_subnets
  private_subnets = var.private_subnets
}

module "iam" {
  source = "../../modules/iam"

  name_prefix = module.tags.name_prefix
  common_tags = module.tags.common_tags

  enable_github_actions_plan_role = var.enable_github_actions_plan_role
  github_oidc_provider_arn        = var.github_oidc_provider_arn
  github_repository               = var.github_repository
  github_branch                   = var.github_branch

  enable_jenkins_plan_role  = var.enable_jenkins_plan_role
  jenkins_trusted_role_arns = var.jenkins_trusted_role_arns
}

module "ecr" {
  source = "../../modules/ecr"

  name_prefix  = module.tags.name_prefix
  common_tags  = module.tags.common_tags
  repositories = var.ecr_repositories
}

module "budget" {
  source = "../../modules/budget"

  name_prefix = module.tags.name_prefix
  common_tags = module.tags.common_tags

  enable_budget                = var.enable_monthly_budget
  monthly_budget_limit_usd     = var.monthly_budget_limit_usd
  enable_budget_notifications  = var.enable_budget_notifications
  notification_email_addresses = var.budget_notification_email_addresses
}

module "cloudwatch" {
  source = "../../modules/cloudwatch"

  project_name = var.project_name
  environment  = var.environment
  name_prefix  = module.tags.name_prefix
  common_tags  = module.tags.common_tags
  log_groups   = var.cloudwatch_log_groups
}

output "vpc_id" {
  description = "ID of the dev VPC baseline."
  value       = module.vpc.vpc_id
}

output "public_subnet_ids" {
  description = "IDs of dev public subnets keyed by logical zone suffix."
  value       = module.vpc.public_subnet_ids
}

output "private_subnet_ids" {
  description = "IDs of dev private subnets keyed by logical zone suffix."
  value       = module.vpc.private_subnet_ids
}

output "app_security_group_id" {
  description = "ID of the baseline application security group."
  value       = module.vpc.app_security_group_id
}

output "database_security_group_id" {
  description = "ID of the baseline database security group."
  value       = module.vpc.database_security_group_id
}

output "nat_gateway_enabled" {
  description = "Confirms that the dev networking baseline does not create NAT Gateway resources."
  value       = module.vpc.nat_gateway_enabled
}


output "iam_terraform_plan_policy_arn" {
  description = "ARN of the read-only Terraform plan policy for future CI/CD validation."
  value       = module.iam.terraform_plan_policy_arn
}

output "github_actions_plan_role_arn" {
  description = "ARN of the optional GitHub Actions plan role. Null until enabled."
  value       = module.iam.github_actions_plan_role_arn
}

output "jenkins_plan_role_arn" {
  description = "ARN of the optional Jenkins plan role. Null until enabled."
  value       = module.iam.jenkins_plan_role_arn
}

output "iam_access_keys_created" {
  description = "Safety signal confirming that the IAM baseline does not create access keys."
  value       = module.iam.access_keys_created
}

output "iam_administrator_access_attached" {
  description = "Safety signal confirming that the IAM baseline does not attach AdministratorAccess."
  value       = module.iam.administrator_access_attached
}

output "ecr_repository_names" {
  description = "ECR repository names keyed by component."
  value       = module.ecr.repository_names
}

output "ecr_repository_urls" {
  description = "ECR repository URLs keyed by component."
  value       = module.ecr.repository_urls
}

output "ecr_repository_arns" {
  description = "ECR repository ARNs keyed by component."
  value       = module.ecr.repository_arns
}

output "ecr_scan_on_push_enabled" {
  description = "Scan-on-push setting for each ECR repository."
  value       = module.ecr.scan_on_push_enabled
}

output "ecr_lifecycle_policy_max_image_count" {
  description = "Maximum number of images retained by lifecycle policy for each ECR repository."
  value       = module.ecr.lifecycle_policy_max_image_count
}

output "monthly_budget_name" {
  description = "Name of the AWS Budget guardrail for the dev environment."
  value       = module.budget.budget_name
}

output "monthly_budget_limit_usd" {
  description = "Configured monthly AWS Budget limit in USD."
  value       = module.budget.monthly_budget_limit_usd
}

output "budget_notifications_enabled" {
  description = "Whether AWS Budget email notifications are enabled."
  value       = module.budget.notifications_enabled
}

output "budget_notification_email_count" {
  description = "Number of configured AWS Budget notification email recipients without exposing addresses."
  value       = module.budget.notification_email_count
}

output "budget_private_notification_data_committed" {
  description = "Safety signal confirming that committed examples do not contain private notification addresses."
  value       = module.budget.private_notification_data_committed
}


output "cloudwatch_log_group_names" {
  description = "CloudWatch log group names keyed by component."
  value       = module.cloudwatch.log_group_names
}

output "cloudwatch_log_group_arns" {
  description = "CloudWatch log group ARNs keyed by component."
  value       = module.cloudwatch.log_group_arns
}

output "cloudwatch_retention_in_days" {
  description = "CloudWatch log retention in days keyed by component."
  value       = module.cloudwatch.retention_in_days
}

output "cloudwatch_log_group_count" {
  description = "Number of CloudWatch log groups defined by the baseline module."
  value       = module.cloudwatch.log_group_count
}

output "cloudwatch_enterprise_observability_enabled" {
  description = "Safety signal confirming this is only a logging baseline, not a full enterprise observability stack."
  value       = module.cloudwatch.enterprise_observability_enabled
}
