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
| `aws-console-iam.png` | AWS Console screenshot for IAM delivery policy/role baseline. | Optional but recommended |
| `aws-console-budget.png` | AWS Console screenshot for budget/cost guardrail. | Optional but recommended |
| `aws-console-cloudwatch.png` | AWS Console screenshot for CloudWatch log groups. | Optional but recommended |

## Safety rules

- Do not commit `.terraform/`, `terraform.tfstate`, `terraform.tfstate.backup`, binary plan files such as `tfplan`, crash logs, local override files, private `.tfvars` files, or real secrets.
- Redact AWS account IDs, real ARNs, email addresses, and console URLs if they expose private data.
- Run `terraform destroy` during the same showcase window unless there is a documented reason not to.
- Keep the showcase short and controlled. This is evidence, not a permanent environment.

## Suggested capture flow

```mermaid
flowchart TD
    A[Prepare evidence folder] --> B[Format Terraform]
    B --> C[Initialize dev environment]
    C --> D[Validate Terraform config]
    D --> E[Create temporary binary</br>plan outside the repo]
    E --> F[Export plan evidence]
    F --> G[Apply during controlled</br>showcase window]
    G --> H[Capture Terraform outputs]
    H --> I[Capture sanitized</br>AWS Console screenshots]
    I --> J[Destroy showcase resources in the same window]
    J --> K[Confirm Terraform state</br>is empty after destroy]
    K --> L[Remove temporary binary plan]

    D -. evidence .-> D1[terraform-validate.txt]
    F -. evidence .-> F1[terraform-plan-dev.txt]
    G -. evidence .-> G1[terraform-apply.txt]
    I -. evidence .-> I1[AWS Console screenshots]
    J -. evidence .-> J1[terraform-destroy.txt]

    E -. local only .-> E1["/tmp/retailops-dev.tfplan"]
    L -. cleanup .-> E1
```
