output "cluster_name" {
  description = "EKS cluster name."
  value       = aws_eks_cluster.this.name
}

output "cluster_id" {
  description = "EKS cluster ID."
  value       = aws_eks_cluster.this.id
}

output "cluster_arn" {
  description = "EKS cluster ARN."
  value       = aws_eks_cluster.this.arn
}

output "cluster_version" {
  description = "Configured Kubernetes version for the EKS cluster."
  value       = aws_eks_cluster.this.version
}

output "cluster_platform_version" {
  description = "EKS platform version reported by AWS after cluster creation."
  value       = aws_eks_cluster.this.platform_version
}

output "cluster_endpoint" {
  description = "EKS API endpoint."
  value       = aws_eks_cluster.this.endpoint
}

output "cluster_certificate_authority_data" {
  description = "Base64-encoded EKS cluster certificate authority data for kubeconfig generation."
  value       = aws_eks_cluster.this.certificate_authority[0].data
  sensitive   = true
}

output "cluster_security_group_id" {
  description = "Security group created by EKS for the cluster control plane."
  value       = aws_eks_cluster.this.vpc_config[0].cluster_security_group_id
}

output "cluster_oidc_issuer_url" {
  description = "OIDC issuer URL for future IRSA/OIDC integration."
  value       = try(aws_eks_cluster.this.identity[0].oidc[0].issuer, null)
}

output "cloudwatch_log_group_name" {
  description = "EKS control plane CloudWatch log group name when managed by this module."
  value       = try(aws_cloudwatch_log_group.cluster[0].name, null)
}

output "kubeconfig_update_command" {
  description = "AWS CLI command for updating local kubeconfig after a real EKS apply."
  value       = "aws eks update-kubeconfig --name ${aws_eks_cluster.this.name}"
}

output "module_tags" {
  description = "Effective tags applied by this module."
  value       = local.common_tags
}

output "cluster_secrets_kms_key_arn" {
  description = "KMS key ARN used by the EKS cluster for Kubernetes secrets encryption."
  value       = local.cluster_secrets_kms_key_arn
}

output "cluster_public_endpoint_enabled" {
  description = "Whether the EKS public API endpoint is enabled. Defaults to false for a private-endpoint-first baseline."
  value       = var.endpoint_public_access
}

output "control_plane_log_types" {
  description = "EKS control plane log types enabled by this module."
  value       = var.enabled_cluster_log_types
}
