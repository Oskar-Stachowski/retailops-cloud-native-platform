output "name_prefix" {
  description = "Standard name prefix for future AWS resources."
  value       = local.name_prefix
}

output "required_tags" {
  description = "Mandatory governance and FinOps tags."
  value       = local.required_tags
}

output "common_tags" {
  description = "Mandatory tags merged with additional non-sensitive tags."
  value       = local.common_tags
}
