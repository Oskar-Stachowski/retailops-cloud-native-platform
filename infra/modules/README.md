# Terraform Modules

This directory contains reusable Terraform modules for the RetailOps AWS foundation.

Current modules:

| Module | Purpose | Current maturity |
|---|---|---|
| `tags` | Produces shared naming and tagging outputs for all future AWS resources. | Active governance module |
| `vpc` | Defines the dev networking baseline: VPC, public/private subnets, route tables, Internet Gateway, and baseline security groups. | Plan-only infrastructure baseline |
| `iam` | Defines a controlled IAM baseline for future Terraform plan validation and CI/CD trust patterns. | Plan-only security baseline |
| `ecr` | Defines container image repositories and lifecycle policies for API and frontend images. | Plan-only delivery foundation |
| `budget` | Defines a monthly AWS Budget guardrail for early FinOps and cost-control evidence. | Plan-only FinOps baseline |
| `cloudwatch` | Defines short-retention CloudWatch Log Groups for the minimal AWS-native logging baseline. | Plan-only observability baseline |

Module implementation should remain incremental. New modules should be added only when the corresponding AWS resource scope, cost impact, security assumptions, and validation path are clear.
