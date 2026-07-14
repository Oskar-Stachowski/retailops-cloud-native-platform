variable "name_prefix" {
  description = "Standard name prefix using <project>-<environment>."
  type        = string

  validation {
    condition     = length(trimspace(var.name_prefix)) > 0
    error_message = "name_prefix must not be empty."
  }
}

variable "common_tags" {
  description = "Common governance and FinOps tags produced by the shared tags module."
  type        = map(string)
  default     = {}
}

variable "vpc_cidr_block" {
  description = "CIDR block for the baseline VPC."
  type        = string
  default     = "10.20.0.0/16"

  validation {
    condition     = can(cidrnetmask(var.vpc_cidr_block))
    error_message = "vpc_cidr_block must be a valid CIDR block."
  }
}

variable "enable_dns_support" {
  description = "Whether DNS support is enabled for the VPC."
  type        = bool
  default     = true
}

variable "enable_dns_hostnames" {
  description = "Whether DNS hostnames are enabled for the VPC."
  type        = bool
  default     = true
}

variable "public_subnets" {
  description = "Public subnet definitions keyed by logical zone suffix such as a or b."
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
  description = "Private subnet definitions keyed by logical zone suffix such as a or b. No NAT Gateway is created in this baseline."
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

variable "flow_log_retention_in_days" {
  description = "CloudWatch retention period for VPC Flow Logs. Keep short for the temporary dev baseline."
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
    ], var.flow_log_retention_in_days)
    error_message = "flow_log_retention_in_days must be a valid CloudWatch Logs retention value."
  }
}
