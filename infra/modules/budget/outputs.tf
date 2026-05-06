output "budget_enabled" {
  description = "Whether the monthly budget guardrail is enabled."
  value       = var.enable_budget
}

output "budget_name" {
  description = "Name of the AWS Budget guardrail."
  value       = try(aws_budgets_budget.monthly_cost[0].name, null)
}

output "budget_arn" {
  description = "ARN of the AWS Budget guardrail."
  value       = try(aws_budgets_budget.monthly_cost[0].arn, null)
}

output "monthly_budget_limit_usd" {
  description = "Monthly AWS Budget limit in USD."
  value       = var.monthly_budget_limit_usd
}

output "notifications_enabled" {
  description = "Whether budget notifications are enabled."
  value       = local.notifications_enabled
}

output "notification_email_count" {
  description = "Number of configured notification email recipients without exposing email addresses."
  value       = local.notification_email_count
}

output "private_notification_data_committed" {
  description = "Safety signal confirming that this module does not require private notification data in committed examples."
  value       = false
}
