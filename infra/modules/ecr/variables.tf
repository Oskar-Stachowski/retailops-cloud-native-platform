variable "name_prefix" {
  description = "Shared name prefix produced by the tags module, for example retailops-dev."
  type        = string
}

variable "common_tags" {
  description = "Common governance and FinOps tags inherited from the tags module."
  type        = map(string)
}

variable "repositories" {
  description = "ECR repositories to create for RetailOps container images."
  type = map(object({
    repository_suffix   = string
    image_tag_mutability = optional(string, "IMMUTABLE")
    scan_on_push        = optional(bool, true)
    max_image_count     = optional(number, 20)
  }))

  default = {
    api = {
      repository_suffix = "api"
    }
    frontend = {
      repository_suffix = "frontend"
    }
  }

  validation {
    condition = alltrue([
      for repository in var.repositories : contains(["MUTABLE", "IMMUTABLE"], repository.image_tag_mutability)
    ])
    error_message = "image_tag_mutability must be either MUTABLE or IMMUTABLE."
  }

  validation {
    condition = alltrue([
      for repository in var.repositories : repository.max_image_count >= 1 && repository.max_image_count <= 100
    ])
    error_message = "max_image_count must be between 1 and 100."
  }

  validation {
    condition = alltrue([
      for repository in var.repositories : can(regex("^[a-z0-9]+([._/-][a-z0-9]+)*$", repository.repository_suffix))
    ])
    error_message = "repository_suffix must be a valid lowercase ECR repository name segment."
  }
}
