output "terraform_plan_policy_name" {
  description = "Name of the read-only Terraform plan policy."
  value       = aws_iam_policy.terraform_plan.name
}

output "terraform_plan_policy_arn" {
  description = "ARN of the read-only Terraform plan policy."
  value       = aws_iam_policy.terraform_plan.arn
}

output "github_actions_plan_role_arn" {
  description = "ARN of the optional GitHub Actions plan role, or null when disabled."
  value       = try(aws_iam_role.github_actions_plan[0].arn, null)
}

output "jenkins_plan_role_arn" {
  description = "ARN of the optional Jenkins plan role, or null when disabled."
  value       = try(aws_iam_role.jenkins_plan[0].arn, null)
}

output "access_keys_created" {
  description = "Safety signal confirming that this IAM baseline does not create access keys."
  value       = false
}

output "administrator_access_attached" {
  description = "Safety signal confirming that this IAM baseline does not attach AdministratorAccess."
  value       = false
}
