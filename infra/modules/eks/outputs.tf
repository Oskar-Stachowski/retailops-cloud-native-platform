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
