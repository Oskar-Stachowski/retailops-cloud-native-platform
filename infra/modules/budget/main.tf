locals {
  budget_name              = "${var.name_prefix}-${var.budget_name_suffix}"
  notification_email_count = length(nonsensitive(var.notification_email_addresses))
  notifications_enabled    = var.enable_budget_notifications && local.notification_email_count > 0

  notification_rules = local.notifications_enabled ? {
    actual = {
      threshold         = var.actual_spend_threshold_percent
      notification_type = "ACTUAL"
    }
    forecasted = {
      threshold         = var.forecasted_spend_threshold_percent
      notification_type = "FORECASTED"
    }
  } : {}

  budget_tags = merge(
    var.common_tags,
    {
      Name      = local.budget_name
      Component = "finops"
      Guardrail = "monthly-budget"
    }
  )
}

resource "aws_budgets_budget" "monthly_cost" {
  count = var.enable_budget ? 1 : 0

  name         = local.budget_name
  budget_type  = "COST"
  limit_amount = format("%.2f", var.monthly_budget_limit_usd)
  limit_unit   = var.limit_unit
  time_unit    = var.time_unit

  dynamic "notification" {
    for_each = local.notification_rules

    content {
      comparison_operator        = "GREATER_THAN"
      threshold                  = notification.value.threshold
      threshold_type             = "PERCENTAGE"
      notification_type          = notification.value.notification_type
      subscriber_email_addresses = var.notification_email_addresses
    }
  }

  tags = local.budget_tags

  lifecycle {
    precondition {
      condition     = !var.enable_budget_notifications || local.notification_email_count > 0
      error_message = "Budget notifications require at least one email address. Keep notifications disabled in committed examples."
    }
  }
}
