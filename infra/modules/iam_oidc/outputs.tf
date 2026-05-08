output "oidc_provider_arn" {
  description = "ARN of the IAM OIDC provider used by future IRSA roles."
  value       = aws_iam_openid_connect_provider.this.arn
}

output "oidc_provider_id" {
  description = "Terraform/AWS ID of the IAM OIDC provider."
  value       = aws_iam_openid_connect_provider.this.id
}

output "oidc_provider_url" {
  description = "Full OIDC issuer URL associated with the EKS cluster."
  value       = aws_iam_openid_connect_provider.this.url
}

output "oidc_provider_host_path" {
  description = "OIDC issuer host/path without https://, used in IRSA trust policy condition keys."
  value       = local.oidc_provider_host_path
}

output "client_id_list" {
  description = "OIDC audiences configured on the IAM OIDC provider."
  value       = aws_iam_openid_connect_provider.this.client_id_list
}

output "thumbprint_list" {
  description = "Thumbprint list configured on the IAM OIDC provider. Empty means the provider was created without explicit thumbprints."
  value       = aws_iam_openid_connect_provider.this.thumbprint_list
}

output "irsa_audience_condition_key" {
  description = "Condition key used by IRSA trust policies to restrict token audience."
  value       = local.irsa_condition_keys.audience
}

output "irsa_subject_condition_key" {
  description = "Condition key used by IRSA trust policies to restrict Kubernetes service account identity."
  value       = local.irsa_condition_keys.subject
}

output "irsa_service_account_subjects" {
  description = "Future Kubernetes service account subjects prepared for IRSA trust policy generation."
  value       = local.service_account_subjects
}

output "irsa_assume_role_policy_json" {
  description = "Optional example trust policy JSON for future IAM roles bound to irsa_service_accounts. Null when no service accounts were provided."
  value       = try(data.aws_iam_policy_document.irsa_assume_role[0].json, null)
}

output "service_account_role_annotation_key" {
  description = "Kubernetes service account annotation key used later to bind a service account to an IAM role ARN."
  value       = "eks.amazonaws.com/role-arn"
}

output "module_tags" {
  description = "Effective tags applied by this module."
  value       = local.common_tags
}
