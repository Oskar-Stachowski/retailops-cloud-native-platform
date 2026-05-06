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
