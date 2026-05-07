output "repository_names" {
  description = "ECR repository names keyed by logical component."
  value = {
    for key, repository in aws_ecr_repository.this : key => repository.name
  }
}

output "repository_arns" {
  description = "ECR repository ARNs keyed by logical component."
  value = {
    for key, repository in aws_ecr_repository.this : key => repository.arn
  }
}

output "repository_urls" {
  description = "ECR repository URLs keyed by logical component."
  value = {
    for key, repository in aws_ecr_repository.this : key => repository.repository_url
  }
}

output "image_tag_mutability" {
  description = "Image tag mutability setting for each ECR repository."
  value = {
    for key, repository in aws_ecr_repository.this : key => repository.image_tag_mutability
  }
}

output "scan_on_push_enabled" {
  description = "Actual scan-on-push setting for each ECR repository."
  value = {
    for key, repository in aws_ecr_repository.this :
    key => repository.image_scanning_configuration[0].scan_on_push
  }
}

output "lifecycle_policy_max_image_count" {
  description = "Maximum number of images retained by the lifecycle policy for each repository."
  value = {
    for key, repository in local.repositories : key => repository.max_image_count
  }
}
