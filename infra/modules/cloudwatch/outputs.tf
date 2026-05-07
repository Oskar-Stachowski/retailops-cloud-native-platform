output "log_group_names" {
  description = "CloudWatch log group names keyed by component."
  value       = { for key, log_group in aws_cloudwatch_log_group.this : key => log_group.name }
}

output "log_group_arns" {
  description = "CloudWatch log group ARNs keyed by component."
  value       = { for key, log_group in aws_cloudwatch_log_group.this : key => log_group.arn }
}

output "retention_in_days" {
  description = "CloudWatch log retention in days keyed by component."
  value       = { for key, log_group in aws_cloudwatch_log_group.this : key => log_group.retention_in_days }
}

output "log_group_count" {
  description = "Number of CloudWatch log groups defined by this baseline module."
  value       = length(aws_cloudwatch_log_group.this)
}

output "enterprise_observability_enabled" {
  description = "Safety signal confirming that this module is only a logging baseline, not a full enterprise observability stack."
  value       = false
}
