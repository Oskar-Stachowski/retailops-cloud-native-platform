variable "project_name" {
  description = "Short project name used in CloudWatch log group names."
  type        = string
}

variable "environment" {
  description = "Environment name used in CloudWatch log group names."
  type        = string
}

variable "name_prefix" {
  description = "Shared resource naming prefix produced by the tags module."
  type        = string
}

variable "common_tags" {
  description = "Shared non-sensitive tags applied to all CloudWatch log groups."
  type        = map(string)
}

variable "log_groups" {
  description = "CloudWatch log groups for the minimal AWS-native observability baseline."
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

  validation {
    condition = alltrue([
      for _, log_group in var.log_groups : contains([
        1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180,
        365, 400, 545, 731, 1096, 1827, 2192, 2557,
        2922, 3288, 3653
      ], log_group.retention_in_days)
    ])
    error_message = "retention_in_days must be a valid CloudWatch Logs retention value. Use 7 days for the Sprint 10 dev baseline unless there is a clear reason to increase it."
  }
}
