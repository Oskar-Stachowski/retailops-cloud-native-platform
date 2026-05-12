locals {
  repositories = {
    for key, repository in var.repositories : key => merge(repository, {
      name = "${var.name_prefix}-${repository.repository_suffix}"
    })
  }
}

resource "aws_ecr_repository" "this" {
  for_each = local.repositories

  # Security baseline: do not expose these as environment-level toggles.
  name                 = each.value.name
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "KMS"
  }

  tags = merge(var.common_tags, {
    Name         = each.value.name
    Component    = each.key
    ResourceType = "ecr-repository"
  })
}

resource "aws_ecr_lifecycle_policy" "this" {
  for_each = local.repositories

  repository = aws_ecr_repository.this[each.key].name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep only the latest ${each.value.max_image_count} images for cost and storage control."
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = each.value.max_image_count
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}
