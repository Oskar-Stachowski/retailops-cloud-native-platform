output "name_prefix" {
  description = "Standard name prefix for future RetailOps AWS resources."
  value       = local.name_prefix
}

output "environment" {
  description = "Current Terraform environment."
  value       = var.environment
}

output "aws_region" {
  description = "Selected AWS region for the future environment."
  value       = var.aws_region
}

output "common_tags" {
  description = "Standard tags to apply to future AWS resources."
  value       = local.common_tags
}
