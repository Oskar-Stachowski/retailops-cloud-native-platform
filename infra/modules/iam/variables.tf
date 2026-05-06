variable "name_prefix" {
  description = "Common name prefix produced by the shared tags module."
  type        = string
}

variable "common_tags" {
  description = "Common non-sensitive tags applied to IAM resources."
  type        = map(string)
}

variable "enable_github_actions_plan_role" {
  description = "Create a future GitHub Actions Terraform plan role when OIDC inputs are provided. Disabled by default."
  type        = bool
  default     = false
}

variable "github_oidc_provider_arn" {
  description = "Existing AWS IAM OIDC provider ARN for GitHub Actions. Keep null until the provider is intentionally created."
  type        = string
  default     = null
}

variable "github_oidc_provider_url" {
  description = "GitHub Actions OIDC issuer URL used in trust policy conditions."
  type        = string
  default     = "https://token.actions.githubusercontent.com"
}

variable "github_repository" {
  description = "GitHub repository allowed to assume the future GitHub Actions plan role, in owner/repository format. Keep null until known."
  type        = string
  default     = null

  validation {
    condition     = var.github_repository == null || can(regex("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", var.github_repository))
    error_message = "github_repository must use owner/repository format when provided."
  }
}

variable "github_branch" {
  description = "Branch allowed to assume the future GitHub Actions plan role."
  type        = string
  default     = "main"
}

variable "enable_jenkins_plan_role" {
  description = "Create a future Jenkins Terraform plan role when trusted AWS principal ARNs are provided. Disabled by default."
  type        = bool
  default     = false
}

variable "jenkins_trusted_role_arns" {
  description = "AWS principal ARNs allowed to assume the future Jenkins plan role. Keep empty until the Jenkins execution identity is known."
  type        = list(string)
  default     = []
}
