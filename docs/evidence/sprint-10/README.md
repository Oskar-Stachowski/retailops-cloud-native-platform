# Sprint 10 AWS Showcase Evidence

This folder stores evidence from a short, controlled AWS showcase window for the RetailOps Terraform and AWS foundation.

The showcase is intentionally temporary. It proves that the Terraform foundation can be planned, applied, inspected in AWS Console, and destroyed without leaving cost-generating resources behind.

## Evidence files

| File | Purpose | Required before final commit? |
|---|---|---:|
| `terraform-validate.txt` | Local Terraform validation result. | Yes |
| `terraform-plan-dev.txt` | Human-readable Terraform plan before apply. | Yes |
| `terraform-apply.txt` | Apply output from the controlled showcase window. | Yes, only if showcase is executed |
| `terraform-outputs.json` | Terraform outputs captured after apply. Redact account-specific values if needed. | Optional |
| `terraform-destroy.txt` | Destroy output proving resources were removed. | Yes, if apply was executed |
| `aws-cleanup-confirmation.md` | Manual cleanup checklist after destroy. | Yes |
| `aws-console-vpc.png` | AWS Console screenshot for VPC/networking resources. | Optional but recommended |
| `aws-console-ecr.png` | AWS Console screenshot for ECR repositories. | Optional but recommended |
| `aws-console-iam-role.png` | AWS Console screenshot for IAM delivery roles/policies. | Optional but recommended |
| `aws-console-budget.png` | AWS Console screenshot for budget/cost guardrail. | Optional but recommended |
| `aws-console-cloudwatch.png` | AWS Console screenshot for CloudWatch log groups. | Optional but recommended |

## Safety rules

- Do not commit `.terraform/`, `terraform.tfstate`, `terraform.tfstate.backup`, crash logs, local override files, or real secrets.
- Redact AWS account IDs, real ARNs, email addresses, and console URLs if they expose private data.
- Run `terraform destroy` during the same showcase window unless there is a documented reason not to.
- Keep the showcase short and controlled. This is evidence, not a permanent environment.

## Suggested capture flow

```bash
mkdir -p docs/evidence/sprint-10 ci-cd/reports/iac

terraform -chdir=infra/environments/dev fmt -recursive
terraform -chdir=infra/environments/dev init -backend=false -input=false
terraform -chdir=infra/environments/dev validate -no-color | tee docs/evidence/sprint-10/terraform-validate.txt
terraform -chdir=infra/environments/dev plan -var-file=terraform.tfvars.example -out=tfplan
terraform -chdir=infra/environments/dev show -no-color tfplan | tee docs/evidence/sprint-10/terraform-plan-dev.txt

terraform -chdir=infra/environments/dev apply -auto-approve tfplan | tee docs/evidence/sprint-10/terraform-apply.txt
terraform -chdir=infra/environments/dev output -json | tee docs/evidence/sprint-10/terraform-outputs.json

# Capture AWS Console screenshots here.

terraform -chdir=infra/environments/dev destroy -var-file=terraform.tfvars.example -auto-approve | tee docs/evidence/sprint-10/terraform-destroy.txt
terraform -chdir=infra/environments/dev state list | tee docs/evidence/sprint-10/terraform-state-after-destroy.txt
```
