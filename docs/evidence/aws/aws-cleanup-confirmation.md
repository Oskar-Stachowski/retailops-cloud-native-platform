# AWS Showcase Cleanup Confirmation - Sprint 10

Historical showcase result. The [2026-09-26 account/state review](2026-09-26-state-drift.md)
found the separately retained GitHub OIDC plan role and no matching foundation
resources or state bucket in the reviewed scope. This document does not claim
that the entire AWS account, unrelated resources or all regions are empty.

## Scope

A short controlled AWS showcase was executed for Sprint 10 Terraform and AWS Foundation evidence.

## Created during showcase

- VPC networking baseline
- Public/private subnets
- Route tables
- Internet Gateway
- Security groups
- ECR repositories
- IAM delivery access baseline
- AWS Budget baseline
- CloudWatch log groups

## Cleanup confirmation

Terraform destroy was executed and captured in:

- `ci-cd/reports/iac/sprint-10-terraform-destroy.txt`

Post-destroy checks:

- Terraform state no longer lists managed resources.
- RetailOps VPC resources were removed.
- RetailOps ECR repositories were removed.
- RetailOps IAM customer-managed policy/roles were removed.
- RetailOps CloudWatch log groups were removed.
- RetailOps Budget resources were removed.

## Notes

Default AWS account resources, such as the default VPC or AWS service-linked roles, were not modified.
No NAT Gateway, EKS, RDS, MSK, OpenSearch, load balancer, or always-on compute resources were intentionally created for this showcase.
