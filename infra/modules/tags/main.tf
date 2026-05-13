locals {
  normalized_project_name = lower(replace(trimspace(var.project_name), " ", "-"))
  normalized_environment  = lower(trimspace(var.environment))

  name_prefix = "${local.normalized_project_name}-${local.normalized_environment}"

  required_tags = {
    Project     = var.project_name
    Service     = "platform"
    Environment = title(local.normalized_environment)
    Owner       = var.owner
    ManagedBy   = var.managed_by
    CostCenter  = var.cost_center
    Lifecycle   = var.resource_lifecycle
  }

  common_tags = merge(local.required_tags, var.additional_tags)
}
