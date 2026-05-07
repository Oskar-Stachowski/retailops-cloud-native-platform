variable "name_prefix" {
  description = "Shared name prefix produced by the tags module, for example retailops-dev."
  type        = string
}

variable "common_tags" {
  description = "Common governance and FinOps tags inherited from the tags module."
  type        = map(string)
}

variable "repositories" {
  description = "ECR repositories to create for RetailOps container images. Security controls enforce immutable tags and scan-on-push."
  type = map(object({
    repository_suffix = string
    max_image_count   = optional(number, 20)
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
