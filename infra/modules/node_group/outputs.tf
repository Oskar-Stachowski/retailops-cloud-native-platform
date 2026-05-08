output "node_group_name" {
  description = "EKS managed node group name."
  value       = aws_eks_node_group.this.node_group_name
}

output "node_group_id" {
  description = "EKS managed node group ID."
  value       = aws_eks_node_group.this.id
}

output "node_group_arn" {
  description = "EKS managed node group ARN."
  value       = aws_eks_node_group.this.arn
}

output "node_group_status" {
  description = "Current EKS managed node group status after creation."
  value       = aws_eks_node_group.this.status
}

output "cluster_name" {
  description = "EKS cluster name used by this node group."
  value       = aws_eks_node_group.this.cluster_name
}

output "node_role_arn" {
  description = "IAM role ARN associated with worker nodes."
  value       = aws_eks_node_group.this.node_role_arn
}

output "subnet_ids" {
  description = "Subnet IDs used by the node group."
  value       = aws_eks_node_group.this.subnet_ids
}

output "instance_types" {
  description = "EC2 instance types configured for the node group."
  value       = aws_eks_node_group.this.instance_types
}

output "capacity_type" {
  description = "Capacity type configured for the node group."
  value       = aws_eks_node_group.this.capacity_type
}

output "ami_type" {
  description = "AMI type configured for the node group."
  value       = aws_eks_node_group.this.ami_type
}

output "scaling_config" {
  description = "Configured scaling boundaries for the node group."
  value = {
    min_size     = aws_eks_node_group.this.scaling_config[0].min_size
    desired_size = aws_eks_node_group.this.scaling_config[0].desired_size
    max_size     = aws_eks_node_group.this.scaling_config[0].max_size
  }
}

output "labels" {
  description = "Effective Kubernetes labels applied to nodes."
  value       = aws_eks_node_group.this.labels
}

output "taints" {
  description = "Effective Kubernetes taints applied to nodes."
  value       = aws_eks_node_group.this.taint
}

output "autoscaling_group_names" {
  description = "Auto Scaling group names backing the managed node group after creation."
  value       = try([for asg in aws_eks_node_group.this.resources[0].autoscaling_groups : asg.name], [])
}

output "remote_access_security_group_id" {
  description = "Remote access security group ID if remote access is enabled. This module does not enable remote access by default, so this is normally null."
  value       = try(aws_eks_node_group.this.resources[0].remote_access_security_group_id, null)
}

output "module_tags" {
  description = "Effective tags applied by this module."
  value       = local.common_tags
}

output "capacity_assumption_summary" {
  description = "Human-readable capacity assumptions useful for plan review evidence."
  value = {
    workload_class = var.workload_class
    capacity_type  = var.capacity_type
    instance_types = var.instance_types
    min_size       = var.min_size
    desired_size   = var.desired_size
    max_size       = var.max_size
    lifecycle      = var.lifecycle
  }
}
