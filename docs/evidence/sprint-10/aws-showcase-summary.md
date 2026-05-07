# Controlled AWS Showcase Summary

## Purpose

This showcase validates that the Sprint 10 Terraform foundation can create a minimal AWS baseline, expose the expected resources in AWS Console, and cleanly destroy the environment afterwards.

## Showcase window

| Field | Value |
|---|---|
| Date | TODO |
| Start time | TODO |
| End time | TODO |
| AWS region | `eu-central-1` |
| Terraform environment | `infra/environments/dev` |
| Terraform var file | `terraform.tfvars.example` |
| Operator | TODO |

## Scope applied

| Area | Expected resources | Status |
|---|---|---|
| Networking | VPC, public/private subnets, route tables, internet gateway, baseline security groups | TODO |
| IAM | Delivery/plan roles and least-privilege policy baseline | TODO |
| ECR | API and frontend repositories with lifecycle policy | TODO |
| Budget | Monthly budget guardrail baseline | TODO |
| CloudWatch | Baseline log groups with short retention | TODO |

## Intentionally excluded

The showcase does not deploy permanent workloads or always-on production services.

| Excluded item | Reason |
|---|---|
| EKS cluster | Deferred until Kubernetes foundation sprint. Avoids unnecessary cost and complexity in Sprint 10. |
| RDS database | Deferred until application/runtime integration requires managed persistence. |
| NAT Gateway | Excluded from the baseline to avoid unnecessary hourly and data processing cost. |
| Load balancer | Deferred until workloads are deployed. |
| OpenSearch/MSK | Deferred as target/future architecture, not Sprint 10 foundation. |
| Managed MLOps services | Deferred until MLOps-specific sprint. |

## Evidence captured

| Evidence | Path | Status |
|---|---|---|
| Terraform validate | `docs/evidence/sprint-10/terraform-validate.txt` | TODO |
| Terraform plan | `docs/evidence/sprint-10/terraform-plan-dev.txt` | TODO |
| Terraform apply | `docs/evidence/sprint-10/terraform-apply.txt` | TODO |
| Terraform destroy | `docs/evidence/sprint-10/terraform-destroy.txt` | TODO |
| VPC screenshot | `docs/evidence/sprint-10/aws-console-vpc.png` | TODO |
| ECR screenshot | `docs/evidence/sprint-10/aws-console-ecr.png` | TODO |
| IAM role screenshot | `docs/evidence/sprint-10/aws-console-iam-role.png` | TODO |
| Budget screenshot | `docs/evidence/sprint-10/aws-console-budget.png` | TODO |
| CloudWatch screenshot | `docs/evidence/sprint-10/aws-console-cloudwatch.png` | TODO |
| Cleanup confirmation | `docs/evidence/sprint-10/aws-cleanup-confirmation.md` | TODO |

## Known security scan notes

| Finding | Decision |
|---|---|
| `CKV_AWS_136` ECR KMS encryption | TODO: document whether this is fixed with a KMS key or accepted for the temporary dev showcase with AES256 only. |
| `CKV_AWS_356` wildcard resource for read/list/describe policy | TODO: document whether this remains an accepted exception for read-only Terraform plan discovery actions that often require `*`. |

## Outcome

TODO: Replace this section after the showcase.

Example:

> The Sprint 10 AWS foundation was applied successfully, inspected in AWS Console, and destroyed during the same controlled showcase window. No production workloads were deployed. No long-running expensive services were intentionally left active.
