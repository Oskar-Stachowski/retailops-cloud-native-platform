variable "project_name" {
  description = "Project name used in node group naming and tags."
  type        = string

  validation {
    condition     = length(trimspace(var.project_name)) > 0
    error_message = "project_name must not be empty."
  }
}

variable "environment" {
  description = "Environment name used in node group naming, labels, and tags, for example dev, staging, or prod-like."
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
    condition     = var.name_prefix == null || can(regex("^[a-zA-Z0-9][a-zA-Z0-9-]{1,50}$", var.name_prefix))
    error_message = "name_prefix must start with an alphanumeric character and contain only letters, numbers, and hyphens."
  }
}

variable "cluster_name" {
  description = "Existing EKS cluster name where this managed node group will be attached. Usually module.eks.cluster_name."
  type        = string

  validation {
    condition     = can(regex("^[a-zA-Z0-9][a-zA-Z0-9-_]{0,99}$", var.cluster_name))
    error_message = "cluster_name must be a valid EKS cluster name and must not exceed 100 characters."
  }
}

variable "node_group_name" {
  description = "Optional explicit EKS managed node group name. When null, the module uses <name_prefix>-<node_group_purpose>-ng."
  type        = string
  default     = null

  validation {
    condition     = var.node_group_name == null || can(regex("^[a-zA-Z0-9][a-zA-Z0-9-_]{0,62}$", var.node_group_name))
    error_message = "node_group_name must start with an alphanumeric character and be 63 characters or shorter."
  }
}

variable "node_group_purpose" {
  description = "Short purpose label for the node group, for example general, platform, app, spot, ml, or observability."
  type        = string
  default     = "general"

  validation {
    condition     = can(regex("^[a-zA-Z0-9][a-zA-Z0-9-_]{1,30}$", var.node_group_purpose))
    error_message = "node_group_purpose must start with an alphanumeric character and contain only letters, numbers, hyphens, or underscores."
  }
}

variable "workload_class" {
  description = "Workload class used in labels and tags. It describes the primary workloads expected on this node group."
  type        = string
  default     = "platform"

  validation {
    condition     = contains(["platform", "application", "observability", "ml", "batch", "system"], var.workload_class)
    error_message = "workload_class must be one of: platform, application, observability, ml, batch, system."
  }
}

variable "node_role_arn" {
  description = "IAM role ARN associated with worker nodes. The role is intentionally provided by an IAM module or environment layer."
  type        = string

  validation {
    condition     = can(regex("^arn:aws[a-zA-Z-]*:iam::[0-9]{12}:role/.+", var.node_role_arn))
    error_message = "node_role_arn must be a valid IAM role ARN."
  }
}

variable "subnet_ids" {
  description = "Subnet IDs where worker nodes will be launched. Prefer private subnets across at least two Availability Zones for realistic EKS validation."
  type        = list(string)

  validation {
    condition     = length(var.subnet_ids) >= 1
    error_message = "subnet_ids must contain at least one subnet ID."
  }

  validation {
    condition     = alltrue([for subnet_id in var.subnet_ids : can(regex("^subnet-[a-zA-Z0-9]+$", subnet_id))])
    error_message = "Every subnet_ids value must look like an AWS subnet ID."
  }
}

variable "kubernetes_version" {
  description = "Optional Kubernetes minor version for managed nodes. When null, AWS uses the cluster version."
  type        = string
  default     = null

  validation {
    condition     = var.kubernetes_version == null || can(regex("^1\\.[0-9]{2}$", var.kubernetes_version))
    error_message = "kubernetes_version must be null or use minor-version format such as 1.33."
  }
}

variable "release_version" {
  description = "Optional AMI release version. Leave null unless a controlled node AMI patch validation requires pinning."
  type        = string
  default     = null

  validation {
    condition     = var.release_version == null || length(trimspace(var.release_version)) > 0
    error_message = "release_version must be null or a non-empty string."
  }
}

variable "ami_type" {
  description = "AMI type for the managed node group. Default uses Amazon Linux 2023 x86_64 standard EKS optimized AMI."
  type        = string
  default     = "AL2023_x86_64_STANDARD"

  validation {
    condition     = length(trimspace(var.ami_type)) > 0
    error_message = "ami_type must not be empty."
  }
}

variable "capacity_type" {
  description = "Managed node group capacity type. Use ON_DEMAND for stable platform/system workloads; use SPOT only for interruption-tolerant workloads."
  type        = string
  default     = "ON_DEMAND"

  validation {
    condition     = contains(["ON_DEMAND", "SPOT"], var.capacity_type)
    error_message = "capacity_type must be ON_DEMAND or SPOT for this module version."
  }
}

variable "instance_types" {
  description = "EC2 instance types for the node group. Keep small for dev validation; use multiple similar types for SPOT."
  type        = list(string)
  default     = ["t3.small"]

  validation {
    condition     = length(var.instance_types) >= 1
    error_message = "instance_types must contain at least one EC2 instance type."
  }

  validation {
    condition     = alltrue([for instance_type in var.instance_types : can(regex("^[a-z0-9]+[a-z0-9]*[.][a-z0-9]+$", instance_type))])
    error_message = "Every instance_types value must look like an EC2 instance type, for example t3.small."
  }
}

variable "disk_size" {
  description = "Root EBS volume size in GiB for nodes when no launch template is used."
  type        = number
  default     = 20

  validation {
    condition     = var.disk_size >= 20 && var.disk_size <= 100
    error_message = "disk_size must be between 20 and 100 GiB for this cost-aware module."
  }
}

variable "min_size" {
  description = "Minimum number of nodes in the managed node group."
  type        = number
  default     = 0

  validation {
    condition     = var.min_size >= 0 && floor(var.min_size) == var.min_size
    error_message = "min_size must be a non-negative integer."
  }
}

variable "desired_size" {
  description = "Desired number of nodes at creation time. Terraform intentionally ignores later desired_size drift so a future autoscaler can manage it."
  type        = number
  default     = 1

  validation {
    condition     = var.desired_size >= 0 && floor(var.desired_size) == var.desired_size
    error_message = "desired_size must be a non-negative integer."
  }
}

variable "max_size" {
  description = "Maximum number of nodes in the managed node group."
  type        = number
  default     = 2

  validation {
    condition     = var.max_size >= 1 && floor(var.max_size) == var.max_size
    error_message = "max_size must be a positive integer."
  }
}

variable "update_max_unavailable" {
  description = "Maximum number of unavailable nodes during a managed node group update. Ignored when update_max_unavailable_percentage is set."
  type        = number
  default     = 1

  validation {
    condition     = var.update_max_unavailable >= 1 && floor(var.update_max_unavailable) == var.update_max_unavailable
    error_message = "update_max_unavailable must be a positive integer."
  }
}

variable "update_max_unavailable_percentage" {
  description = "Optional maximum percentage of unavailable nodes during update. When set, update_max_unavailable is not used."
  type        = number
  default     = null

  validation {
    condition     = var.update_max_unavailable_percentage == null || (var.update_max_unavailable_percentage >= 1 && var.update_max_unavailable_percentage <= 100 && floor(var.update_max_unavailable_percentage) == var.update_max_unavailable_percentage)
    error_message = "update_max_unavailable_percentage must be null or an integer between 1 and 100."
  }
}

variable "labels" {
  description = "Additional Kubernetes labels applied to nodes in the managed node group. Values here can override default module labels."
  type        = map(string)
  default     = {}

  validation {
    condition     = alltrue([for key, value in var.labels : length(trimspace(key)) > 0 && length(trimspace(value)) > 0])
    error_message = "labels must not contain empty keys or empty values."
  }
}

variable "taints" {
  description = "Optional Kubernetes taints applied to nodes. Use for dedicated node groups such as observability, ml, or spot workloads."
  type = list(object({
    key    = string
    value  = optional(string)
    effect = string
  }))
  default = []

  validation {
    condition     = alltrue([for taint in var.taints : length(trimspace(taint.key)) > 0])
    error_message = "Every taint must have a non-empty key."
  }

  validation {
    condition     = alltrue([for taint in var.taints : contains(["NO_SCHEDULE", "NO_EXECUTE", "PREFER_NO_SCHEDULE"], taint.effect)])
    error_message = "Every taint effect must be NO_SCHEDULE, NO_EXECUTE, or PREFER_NO_SCHEDULE."
  }
}

variable "force_update_version" {
  description = "Force version update if pods cannot be drained because of a pod disruption budget issue. Keep false unless an explicit maintenance decision is made."
  type        = bool
  default     = false
}

variable "lifecycle" {
  description = "Cost-control lifecycle tag. Use temporary for short-lived EKS validation node groups."
  type        = string
  default     = "temporary"

  validation {
    condition     = contains(["temporary", "persistent"], var.lifecycle)
    error_message = "lifecycle must be temporary or persistent."
  }
}

variable "tags" {
  description = "Additional tags merged with module defaults. Values here can override default tag values when intentionally needed."
  type        = map(string)
  default     = {}
}
