# VPC Module

This module defines the first AWS networking baseline for the RetailOps dev environment.

It creates:

- one VPC,
- public subnets,
- private subnets,
- one Internet Gateway,
- one public route table with an Internet route,
- private route tables without NAT Gateway routes,
- a restricted default security group with no ingress or egress rules,
- VPC Flow Logs for accepted and rejected traffic,
- a short-retention CloudWatch log group encrypted with a dedicated rotating KMS key,
- a least-privilege service role allowing VPC Flow Logs to write to that log group.

Workload security groups are intentionally not created here. They belong next
to the compute or database resources that actually attach them; creating
unattached placeholder groups would provide no enforcement.

## Cost-control decision

This module intentionally does **not** create a NAT Gateway. NAT Gateway is useful for private subnet outbound Internet access, but it has an always-on cost profile. The current private route tables have no Internet egress, and this module does
not create VPC endpoints. A private compute deployment must add and verify its
required AWS-service and image-registry connectivity.

## Tagging

Governance tags are inherited through the environment provider `default_tags` configuration using the shared `tags` module. Resource-level tags in this module set only the AWS `Name` tag to avoid duplicating provider-level default tags.

## Safety

Use the [infrastructure validation guide](../../guides/infrastructure.md).
Integrate and deploy this network according to the
[AWS activation plan](../../plans/aws-activation.md).
