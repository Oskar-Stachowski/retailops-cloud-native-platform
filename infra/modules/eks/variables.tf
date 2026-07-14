variable "project_name" {
  description = "Project name used in cluster naming and tags."
  type        = string

  validation {
    condition     = length(trimspace(var.project_name)) > 0
    error_message = "project_name must not be empty."
  }
}

variable "environment" {
  description = "Environment name used in cluster naming and tags, for example dev, staging, or prod-like."
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
  description = "Optional explicit EKS cluster name. When null, the module uses <name_prefix>-eks."
  type        = string
  default     = null

  validation {
    condition     = var.cluster_name == null || can(regex("^[a-zA-Z0-9][a-zA-Z0-9-_]{0,99}$", var.cluster_name))
    error_message = "cluster_name must be a valid EKS cluster name and must not exceed 100 characters."
  }
}

variable "cluster_role_arn" {
  description = "IAM role ARN used by the EKS control plane. The role is intentionally provided by an IAM module or environment layer."
  type        = string

  validation {
    condition     = can(regex("^arn:aws[a-zA-Z-]*:iam::[0-9]{12}:role/.+", var.cluster_role_arn))
    error_message = "cluster_role_arn must be a valid IAM role ARN."
  }
}

variable "subnet_ids" {
  description = "Subnet IDs where the EKS control plane creates network interfaces. Use at least two subnets across availability zones."
  type        = list(string)

  validation {
    condition     = length(var.subnet_ids) >= 2
    error_message = "subnet_ids must contain at least two subnet IDs."
  }

  validation {
    condition     = alltrue([for subnet_id in var.subnet_ids : can(regex("^subnet-[a-zA-Z0-9]+$", subnet_id))])
    error_message = "Every subnet_ids value must look like an AWS subnet ID."
  }
}

variable "cluster_security_group_ids" {
  description = "Additional security groups attached to the EKS control plane. Leave empty until a dedicated security group module is wired."
  type        = list(string)
  default     = []

  validation {
    condition     = alltrue([for security_group_id in var.cluster_security_group_ids : can(regex("^sg-[a-zA-Z0-9]+$", security_group_id))])
    error_message = "Every cluster_security_group_ids value must look like an AWS security group ID."
  }
}

variable "kubernetes_version" {
  description = "EKS Kubernetes minor version. Keep this on standard support; avoid extended support for portfolio dev clusters."
  type        = string
  default     = "1.33"

  validation {
    condition     = can(regex("^1\\.[0-9]{2}$", var.kubernetes_version))
    error_message = "kubernetes_version must use minor-version format such as 1.33."
  }
}

variable "upgrade_support_type" {
  description = "EKS upgrade support policy. STANDARD avoids extended-support cost for old Kubernetes versions."
  type        = string
  default     = "STANDARD"

  validation {
    condition     = contains(["STANDARD", "EXTENDED"], var.upgrade_support_type)
    error_message = "upgrade_support_type must be STANDARD or EXTENDED."
  }
}

variable "authentication_mode" {
  description = "EKS cluster authentication mode. API_AND_CONFIG_MAP keeps compatibility while the project transitions toward access entries."
  type        = string
  default     = "API_AND_CONFIG_MAP"

  validation {
    condition     = contains(["CONFIG_MAP", "API", "API_AND_CONFIG_MAP"], var.authentication_mode)
    error_message = "authentication_mode must be CONFIG_MAP, API, or API_AND_CONFIG_MAP."
  }
}

variable "bootstrap_cluster_creator_admin_permissions" {
  description = "Grant temporary admin access to the principal creating the cluster. Keep explicit so access behavior is not hidden."
  type        = bool
  default     = true
}

variable "endpoint_private_access" {
  description = "Whether the EKS API endpoint is reachable from inside the VPC."
  type        = bool
  default     = true
}

variable "endpoint_public_access" {
  description = "Whether the EKS API endpoint is reachable from public networks. Defaults to false so the module is private-endpoint-first and passes the EKS public endpoint Checkov gate."
  type        = bool
  default     = false
}

variable "public_access_cidrs" {
  description = "CIDR blocks allowed to reach the public EKS API endpoint when endpoint_public_access=true. Leave empty for private-only clusters."
  type        = list(string)
  default     = []

  validation {
    condition     = alltrue([for cidr in var.public_access_cidrs : can(cidrhost(cidr, 0))])
    error_message = "public_access_cidrs must contain valid CIDR blocks."
  }

  validation {
    condition     = !contains(var.public_access_cidrs, "0.0.0.0/0")
    error_message = "Do not expose the EKS public endpoint to 0.0.0.0/0. Use a trusted /32 or disable public access."
  }
}

variable "ip_family" {
  description = "IP family for Kubernetes service networking. IPv4 is the default for the early RetailOps EKS foundation."
  type        = string
  default     = "ipv4"

  validation {
    condition     = contains(["ipv4", "ipv6"], var.ip_family)
    error_message = "ip_family must be ipv4 or ipv6."
  }
}

variable "service_ipv4_cidr" {
  description = "Optional Kubernetes service IPv4 CIDR. Leave null unless the environment needs an explicit non-overlapping service range."
  type        = string
  default     = null

  validation {
    condition     = var.service_ipv4_cidr == null || can(cidrhost(var.service_ipv4_cidr, 0))
    error_message = "service_ipv4_cidr must be null or a valid IPv4 CIDR block."
  }
}

variable "enabled_cluster_log_types" {
  description = "EKS control plane log types. API, audit, and authenticator logs are enabled by default to avoid a silent control-plane baseline and to prevent scanner edge-cases around an empty list."
  type        = list(string)
  default     = ["api", "audit", "authenticator"]

  validation {
    condition = alltrue([
      for log_type in var.enabled_cluster_log_types : contains([
        "api",
        "audit",
        "authenticator",
        "controllerManager",
        "scheduler",
      ], log_type)
    ])
    error_message = "enabled_cluster_log_types can include only api, audit, authenticator, controllerManager, and scheduler."
  }
}

variable "create_cloudwatch_log_group" {
  description = "Create the EKS control plane CloudWatch log group with explicit retention and KMS encryption. Required when enabled_cluster_log_types is not empty."
  type        = bool
  default     = true
}

variable "cloudwatch_log_retention_in_days" {
  description = "Retention for the EKS control plane CloudWatch log group when create_cloudwatch_log_group is true."
  type        = number
  default     = 7

  validation {
    condition = contains([
      1,
      3,
      5,
      7,
      14,
      30,
      60,
      90,
      120,
      150,
      180,
      365,
      400,
      545,
      731,
      1096,
      1827,
      2192,
      2557,
      2922,
      3288,
      3653,
    ], var.cloudwatch_log_retention_in_days)
    error_message = "cloudwatch_log_retention_in_days must be a valid CloudWatch Logs retention value."
  }
}


variable "create_cluster_secrets_kms_key" {
  description = "Create a dedicated KMS key for EKS Kubernetes secrets encryption. Set false only when cluster_secrets_kms_key_arn points to an existing customer managed key."
  type        = bool
  default     = true
}

variable "cluster_secrets_kms_key_arn" {
  description = "Existing customer managed KMS key ARN for EKS Kubernetes secrets encryption. Leave null to let this module create a dedicated key."
  type        = string
  default     = null

  validation {
    condition     = var.cluster_secrets_kms_key_arn == null || can(regex("^arn:aws[a-zA-Z-]*:kms:[a-z0-9-]+:[0-9]{12}:key/[a-f0-9-]+$", var.cluster_secrets_kms_key_arn))
    error_message = "cluster_secrets_kms_key_arn must be null or a valid AWS KMS key ARN."
  }
}

variable "cloudwatch_log_group_kms_key_id" {
  description = "Optional KMS key ID or ARN for the EKS control plane CloudWatch log group. Defaults to the EKS secrets encryption key."
  type        = string
  default     = null
}

variable "kms_key_deletion_window_in_days" {
  description = "Waiting period before deleting the module-managed KMS key. Keep short for temporary portfolio validation clusters."
  type        = number
  default     = 7

  validation {
    condition     = var.kms_key_deletion_window_in_days >= 7 && var.kms_key_deletion_window_in_days <= 30
    error_message = "kms_key_deletion_window_in_days must be between 7 and 30."
  }
}

variable "resource_lifecycle" {
  description = "Cost-control lifecycle tag. Use temporary for short-lived EKS validation clusters."
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

check "eks_kms_key_source" {
  assert {
    condition     = var.create_cluster_secrets_kms_key || var.cluster_secrets_kms_key_arn != null
    error_message = "Either create_cluster_secrets_kms_key must be true or cluster_secrets_kms_key_arn must point to an existing customer managed KMS key."
  }
}
