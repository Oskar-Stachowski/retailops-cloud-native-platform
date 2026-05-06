locals {
  repositories = {
    for key, repository in var.repositories : key => merge(repository, {
      name = "${var.name_prefix}-${repository.repository_suffix}"
    })
  }
}

resource "aws_ecr_repository" "this" {
  for_each = local.repositories

  name                 = each.value.name
  image_tag_mutability = each.value.image_tag_mutability

  image_scanning_configuration {
    scan_on_push = each.value.scan_on_push
  }

  encryption_configuration {
    encryption_type = "AES256"
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
