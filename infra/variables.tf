variable "project_name" {
  description = "Short project name used for naming and tagging AWS resources."
  type        = string
  default     = "retailops"

  validation {
    condition     = length(trimspace(var.project_name)) > 0
    error_message = "project_name must not be empty."
  }
}

variable "environment" {
  description = "Deployment environment name. Commit 1 uses dev only."
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod."
  }
}

variable "aws_region" {
  description = "AWS region selected for the future environment. No resources are created in Commit 1."
  type        = string
  default     = "eu-central-1"
}

variable "owner" {
  description = "Human owner used for cost and responsibility tagging."
  type        = string
  default     = "oskar"
}

variable "cost_center" {
  description = "Cost allocation tag. For this portfolio project the default is portfolio."
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

  validation {
    condition     = contains(["temporary", "persistent"], var.resource_lifecycle)
    error_message = "lifecycle must be either temporary or persistent."
  }
}

variable "additional_tags" {
  description = "Additional non-sensitive tags merged into common_tags."
  type        = map(string)
  default     = {}
}
