locals {
  normalized_log_groups = {
    for key, log_group in var.log_groups : key => {
      name              = "/${var.project_name}/${var.environment}/${log_group.name_suffix}"
      retention_in_days = log_group.retention_in_days
      kms_key_id        = try(log_group.kms_key_id, null)
      skip_destroy      = try(log_group.skip_destroy, false)
    }
  }
}

resource "aws_cloudwatch_log_group" "this" {
  for_each = local.normalized_log_groups

  name              = each.value.name
  retention_in_days = each.value.retention_in_days
  kms_key_id        = each.value.kms_key_id
  skip_destroy      = each.value.skip_destroy

  tags = merge(var.common_tags, {
    Name          = "${var.name_prefix}-${each.key}-logs"
    Component     = each.key
    ResourceType  = "cloudwatch-log-group"
    RetentionDays = tostring(each.value.retention_in_days)
  })
}
