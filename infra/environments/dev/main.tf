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

module "vpc" {
  source = "../../modules/vpc"

  name_prefix     = module.tags.name_prefix
  common_tags     = module.tags.common_tags
  vpc_cidr_block  = var.vpc_cidr_block
  public_subnets  = var.public_subnets
  private_subnets = var.private_subnets
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
