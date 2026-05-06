locals {
  normalized_project_name = lower(replace(trimspace(var.project_name), " ", "-"))
  name_prefix             = "${local.normalized_project_name}-${var.environment}"

  common_tags = merge(
    {
      Project     = var.project_name
      Environment = var.environment
      Owner       = var.owner
      ManagedBy   = var.managed_by
      CostCenter  = var.cost_center
      Lifecycle   = var.resource_lifecycle
    },
    var.additional_tags
  )
}
