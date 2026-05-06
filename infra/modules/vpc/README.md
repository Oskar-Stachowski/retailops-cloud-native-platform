# VPC Module

This module defines the first AWS networking baseline for the RetailOps dev environment.

It creates:

- one VPC,
- public subnets,
- private subnets,
- one Internet Gateway,
- one public route table with an Internet route,
- private route tables without NAT Gateway routes,
- baseline application and database security groups.

## Cost-control decision

This module intentionally does **not** create a NAT Gateway. NAT Gateway is useful for private subnet outbound Internet access, but it has an always-on cost profile. For this sprint, private subnets are prepared architecturally, but outbound Internet access from private subnets is deferred.

## Tagging

Governance tags are inherited through the environment provider `default_tags` configuration using the shared `tags` module. Resource-level tags in this module set only the AWS `Name` tag to avoid duplicating provider-level default tags.

## Safety

This module should be validated with `terraform validate` and optionally reviewed with `terraform plan` when AWS credentials are available. Do not run `terraform apply` until a separate apply decision is made.
