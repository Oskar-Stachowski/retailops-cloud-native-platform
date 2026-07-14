variable "project_name" {
  description = "Project name used in IAM OIDC provider tags."
  type        = string

  validation {
    condition     = length(trimspace(var.project_name)) > 0
    error_message = "project_name must not be empty."
  }
}

variable "environment" {
  description = "Environment name used in IAM OIDC provider tags, for example dev, staging, or prod-like."
  type        = string

  validation {
    condition     = can(regex("^[a-zA-Z0-9-]+$", var.environment))
    error_message = "environment may contain only letters, numbers, and hyphens."
  }
}

variable "name_prefix" {
  description = "Optional name prefix. When null, the module uses <project_name>-<environment>."
  type        = string
  default     = null

  validation {
    condition     = var.name_prefix == null || can(regex("^[a-zA-Z0-9][a-zA-Z0-9-]{1,60}$", var.name_prefix))
    error_message = "name_prefix must start with an alphanumeric character and contain only letters, numbers, and hyphens."
  }
}

variable "cluster_name" {
  description = "Optional EKS cluster name used only for tagging and evidence. The OIDC provider is bound by issuer URL, not by this name."
  type        = string
  default     = null

  validation {
    condition     = var.cluster_name == null || can(regex("^[a-zA-Z0-9][a-zA-Z0-9-_]{0,99}$", var.cluster_name))
    error_message = "cluster_name must be null or a valid EKS cluster name up to 100 characters."
  }
}

variable "cluster_oidc_issuer_url" {
  description = "OIDC issuer URL exposed by the EKS cluster, usually module.eks.cluster_oidc_issuer_url."
  type        = string

  validation {
    condition     = can(regex("^https://oidc[.]eks[.][a-z0-9-]+[.]amazonaws[.]com(.cn)?/id/[A-Za-z0-9]+$", trimspace(var.cluster_oidc_issuer_url)))
    error_message = "cluster_oidc_issuer_url must look like an EKS OIDC issuer URL, for example https://oidc.eks.eu-central-1.amazonaws.com/id/EXAMPLE."
  }
}

variable "client_id_list" {
  description = "OIDC audiences allowed for this IAM provider. EKS IRSA normally requires sts.amazonaws.com."
  type        = list(string)
  default     = ["sts.amazonaws.com"]

  validation {
    condition     = length(var.client_id_list) > 0 && alltrue([for client_id in var.client_id_list : length(trimspace(client_id)) > 0])
    error_message = "client_id_list must contain at least one non-empty audience value."
  }
}

variable "thumbprint_list" {
  description = "Optional OIDC provider certificate thumbprints. With recent AWS provider versions this can stay empty for AWS-trusted providers; set explicitly only when required by your account/provider policy."
  type        = list(string)
  default     = []

  validation {
    condition = alltrue([
      for thumbprint in var.thumbprint_list : can(regex("^[A-Fa-f0-9]{40}$", thumbprint))
    ])
    error_message = "Every thumbprint must be a 40-character hexadecimal SHA-1 certificate thumbprint."
  }
}

variable "irsa_service_accounts" {
  description = "Optional future service accounts used only to generate an example IRSA assume-role trust policy. This module does not create IAM roles or Kubernetes service accounts."
  type = list(object({
    namespace = string
    name      = string
  }))
  default = []

  validation {
    condition = alltrue([
      for service_account in var.irsa_service_accounts :
      can(regex("^[a-z0-9]([-a-z0-9]*[a-z0-9])?$", service_account.namespace))
    ])
    error_message = "Every service account namespace must be a valid lowercase Kubernetes DNS label."
  }

  validation {
    condition = alltrue([
      for service_account in var.irsa_service_accounts :
      can(regex("^[a-z0-9]([-a-z0-9]*[a-z0-9])?$", service_account.name))
    ])
    error_message = "Every service account name must be a valid lowercase Kubernetes DNS label."
  }
}

variable "resource_lifecycle" {
  description = "Cost-control lifecycle tag. Use temporary for short-lived EKS validation foundations."
  type        = string
  default     = "temporary"

  validation {
    condition     = contains(["temporary", "persistent"], var.resource_lifecycle)
    error_message = "resource_lifecycle must be temporary or persistent."
  }
}

variable "tags" {
  description = "Additional tags merged with module defaults. Values here can override default tag values when intentionally needed."
  type        = map(string)
  default     = {}
}
