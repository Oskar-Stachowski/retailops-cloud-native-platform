variable "name_prefix" {
  description = "Shared name prefix produced by the tags module."
  type        = string
}

variable "common_tags" {
  description = "Mandatory and additional non-sensitive tags inherited from the shared tags module."
  type        = map(string)
}

variable "enable_budget" {
  description = "Create the monthly AWS Budget guardrail."
  type        = bool
  default     = true
}

variable "monthly_budget_limit_usd" {
  description = "Monthly AWS Budget limit in USD for the dev cost guardrail."
  type        = number
  default     = 10

  validation {
    condition     = var.monthly_budget_limit_usd > 0 && var.monthly_budget_limit_usd <= 100
    error_message = "monthly_budget_limit_usd must be greater than 0 and no higher than 100 for this dev baseline."
  }
}

variable "budget_name_suffix" {
  description = "Suffix used for the AWS Budget name."
  type        = string
  default     = "monthly-cost-guardrail"
}

variable "limit_unit" {
  description = "Currency unit for the AWS Budget limit."
  type        = string
  default     = "USD"

  validation {
    condition     = var.limit_unit == "USD"
    error_message = "This sprint supports USD budgets only."
  }
}

variable "time_unit" {
  description = "Time unit for the AWS Budget."
  type        = string
  default     = "MONTHLY"

  validation {
    condition     = contains(["DAILY", "MONTHLY", "QUARTERLY", "ANNUALLY"], var.time_unit)
    error_message = "time_unit must be one of DAILY, MONTHLY, QUARTERLY, or ANNUALLY."
  }
}

variable "enable_budget_notifications" {
  description = "Enable AWS Budget email notifications. Keep false unless private notification addresses are provided outside the repo."
  type        = bool
  default     = false
}

variable "notification_email_addresses" {
  description = "Email recipients for AWS Budget notifications. Treat as private data and do not commit real addresses."
  type        = list(string)
  default     = []
  sensitive   = true
}

variable "actual_spend_threshold_percent" {
  description = "Actual spend percentage threshold for the budget alert."
  type        = number
  default     = 80

  validation {
    condition     = var.actual_spend_threshold_percent > 0 && var.actual_spend_threshold_percent <= 100
    error_message = "actual_spend_threshold_percent must be between 1 and 100."
  }
}

variable "forecasted_spend_threshold_percent" {
  description = "Forecasted spend percentage threshold for the budget alert."
  type        = number
  default     = 100

  validation {
    condition     = var.forecasted_spend_threshold_percent > 0 && var.forecasted_spend_threshold_percent <= 200
    error_message = "forecasted_spend_threshold_percent must be between 1 and 200."
  }
}
