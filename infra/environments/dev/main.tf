terraform {
  required_version = ">= 1.6.0, < 2.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
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

locals {
  common_tags = merge(
    {
      Project     = var.project_name
      Environment = var.environment
      Owner       = var.owner
      ManagedBy   = var.managed_by
      CostCenter  = var.cost_center
      Lifecycle   = var.resource_lifecycle
    },
    var.additional_tags
  )
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = local.common_tags
  }
}

module "foundation" {
  source = "../.."

  project_name       = var.project_name
  environment        = var.environment
  aws_region         = var.aws_region
  owner              = var.owner
  cost_center        = var.cost_center
  managed_by         = var.managed_by
  resource_lifecycle = var.resource_lifecycle
  additional_tags    = var.additional_tags
}
