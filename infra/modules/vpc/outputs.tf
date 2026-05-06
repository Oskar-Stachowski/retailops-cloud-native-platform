output "vpc_id" {
  description = "ID of the baseline VPC."
  value       = aws_vpc.this.id
}

output "vpc_cidr_block" {
  description = "CIDR block of the baseline VPC."
  value       = aws_vpc.this.cidr_block
}

output "public_subnet_ids" {
  description = "IDs of public subnets keyed by logical zone suffix."
  value       = { for key, subnet in aws_subnet.public : key => subnet.id }
}

output "private_subnet_ids" {
  description = "IDs of private subnets keyed by logical zone suffix."
  value       = { for key, subnet in aws_subnet.private : key => subnet.id }
}

output "public_route_table_id" {
  description = "ID of the public route table."
  value       = aws_route_table.public.id
}

output "private_route_table_ids" {
  description = "IDs of private route tables keyed by logical zone suffix."
  value       = { for key, route_table in aws_route_table.private : key => route_table.id }
}

output "app_security_group_id" {
  description = "ID of the baseline application security group."
  value       = aws_security_group.app.id
}

output "database_security_group_id" {
  description = "ID of the baseline database security group."
  value       = aws_security_group.database.id
}

output "nat_gateway_enabled" {
  description = "Explicit signal that this low-cost baseline does not create NAT Gateway resources."
  value       = false
}

output "common_tags" {
  description = "Common tags passed from the shared tags module for audit visibility."
  value       = var.common_tags
}
