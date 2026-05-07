# AWS Console Screenshot Checklist — Sprint 10 Showcase

Use this checklist during the short showcase window. Screenshots should prove the resources exist, but should not expose account IDs, private ARNs, emails, or secrets.

## Required screenshots

| Screenshot | Suggested AWS Console view | Save as |
|---|---|---|
| VPC baseline | VPC list/details filtered by `retailops-dev-network-vpc` | `docs/evidence/sprint-10/aws-console-vpc.png` |
| ECR repositories | ECR repositories filtered by `retailops` | `docs/evidence/sprint-10/aws-console-ecr.png` |
| IAM delivery role | IAM role/policy view filtered by `retailops-dev` | `docs/evidence/sprint-10/aws-console-iam-role.png` |
| Budget guardrail | AWS Budgets budget details | `docs/evidence/sprint-10/aws-console-budget.png` |
| CloudWatch log groups | CloudWatch Logs groups filtered by `/retailops/dev` | `docs/evidence/sprint-10/aws-console-cloudwatch.png` |

## Screenshot hygiene

- Crop or blur AWS account ID.
- Crop or blur full ARNs if they expose the account ID.
- Do not show access keys, tokens, credentials, or private emails.
- Prefer filtered views showing resource names, tags, and configuration choices.
- Add screenshots only after `terraform apply`; keep them after `terraform destroy` as historical evidence.

## Suggested naming convention

```text
docs/evidence/sprint-10/aws-console-vpc.png
docs/evidence/sprint-10/aws-console-ecr.png
docs/evidence/sprint-10/aws-console-iam-role.png
docs/evidence/sprint-10/aws-console-budget.png
docs/evidence/sprint-10/aws-console-cloudwatch.png
```
