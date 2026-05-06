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
  description = "Deployment environment name used for governance and cost allocation tags."
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod."
  }
}

variable "owner" {
  description = "Human or team owner responsible for the resource."
  type        = string
  default     = "oskar"

  validation {
    condition     = length(trimspace(var.owner)) > 0
    error_message = "owner must not be empty."
  }
}

variable "managed_by" {
  description = "Provisioning method tag. For this project the expected value is terraform."
  type        = string
  default     = "terraform"

  validation {
    condition     = length(trimspace(var.managed_by)) > 0
    error_message = "managed_by must not be empty."
  }
}

variable "cost_center" {
  description = "Cost allocation tag used for portfolio-level cost grouping."
  type        = string
  default     = "portfolio"

  validation {
    condition     = length(trimspace(var.cost_center)) > 0
    error_message = "cost_center must not be empty."
  }
}

variable "resource_lifecycle" {
  description = "Resource lifecycle intent used for cleanup and FinOps decisions."
  type        = string
  default     = "temporary"

  validation {
    condition     = contains(["temporary", "persistent"], var.resource_lifecycle)
    error_message = "resource_lifecycle must be either temporary or persistent."
  }
}

variable "additional_tags" {
  description = "Additional non-sensitive tags merged into common_tags."
  type        = map(string)
  default     = {}
}
