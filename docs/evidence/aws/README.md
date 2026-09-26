# AWS and Terraform Evidence

This folder stores historical AWS showcase evidence and dated reviews of the
RetailOps Terraform foundation, account inventory and state/drift workflow.

The current [2026-09-26 state review](2026-09-26-state-drift.md) distinguishes
empty-state baseline planning from live drift. It preserves the existing GitHub
plan role and prepares an S3/KMS backend without provisioning it. The showcase
screenshots and cleanup notes below retain their original scope and dates.

The showcase is intentionally temporary. It proves that the Terraform foundation can be planned, applied, inspected in AWS Console, and destroyed without leaving cost-generating resources behind.

## Evidence files

| File | Purpose | Required before final commit? |
|---|---|---:|
| `2026-09-26-state-drift.md`, `2026-09-26-state-drift.json` | Scoped account audit, guarded local/OIDC baseline plans, CI tests and explicit S3 activation limits. | Current dated review |
| `aws-cleanup-confirmation.md` | Manual cleanup checklist after destroy. | Yes |
| `aws-console-vpc.png` | AWS Console screenshot for VPC/networking resources. | Optional but recommended |
| `aws-console-ecr.png` | AWS Console screenshot for ECR repositories. | Optional but recommended |
| `aws-console-iam.png` | AWS Console screenshot for IAM delivery policy/role baseline. | Optional but recommended |
| `aws-console-budget.png` | AWS Console screenshot for budget/cost guardrail. | Optional but recommended |
| `aws-console-cloudwatch.png` | AWS Console screenshot for CloudWatch log groups. | Optional but recommended |

The committed Terraform graph SVG files are historical Sprint 10 snapshots.
They describe the infrastructure used during that controlled showcase, not the
current working tree. Regenerate and relabel them only during a future reviewed
plan/showcase; do not treat them as current validation evidence.

Raw or semi-raw Terraform command evidence is intentionally stored under `ci-cd/reports/iac/`:

| File | Purpose | Tracking policy |
|---|---|---|
| `ci-cd/reports/iac/sprint-10-terraform-validate.txt` | Local Terraform validation result. | Tracked curated snapshot |
| `ci-cd/reports/iac/sprint-10-terraform-plan-dev.txt` | Sanitized human-readable Terraform plan summary before apply. | Tracked curated snapshot |
| `ci-cd/reports/iac/sprint-10-terraform-apply.txt` | Sanitized apply evidence from the controlled showcase window. | Tracked curated snapshot |
| `ci-cd/reports/iac/sprint-10-terraform-destroy.txt` | Sanitized destroy evidence proving resources were removed. | Tracked curated snapshot |

## Safety rules

- Do not commit `.terraform/`, `terraform.tfstate`, `terraform.tfstate.backup`, binary plan files such as `tfplan`, crash logs, local override files, private `.tfvars` files, or real secrets.
- Redact AWS account IDs, real ARNs, email addresses, and console URLs if they expose private data.
- Run `terraform destroy` during the same showcase window unless there is a documented reason not to.
- Keep the showcase short and controlled. This is evidence, not a permanent environment.

## Suggested capture flow

```mermaid
flowchart TD
    A[Prepare evidence plan] --> B[Format Terraform]
    B --> C[Initialize dev environment]
    C --> D[Validate Terraform config]
    D --> E[Create temporary binary</br>plan outside the repo]
    E --> F[Export sanitized plan evidence]
    F --> G[Apply during controlled</br>showcase window]
    G --> H[Capture sanitized outputs]
    H --> I[Capture sanitized</br>AWS Console screenshots]
    I --> J[Destroy showcase resources in the same window]
    J --> K[Confirm cleanup]
    K --> L[Remove temporary binary plan]

    D -. raw evidence .-> D1[ci-cd/reports/iac/sprint-10-terraform-validate.txt]
    F -. raw evidence .-> F1[ci-cd/reports/iac/sprint-10-terraform-plan-dev.txt]
    G -. raw evidence .-> G1[ci-cd/reports/iac/sprint-10-terraform-apply.txt]
    I -. curated evidence .-> I1[docs/evidence/aws/*.png]
    J -. raw evidence .-> J1[ci-cd/reports/iac/sprint-10-terraform-destroy.txt]
    K -. curated evidence .-> K1[docs/evidence/aws/aws-cleanup-confirmation.md]

    E -. local only .-> E1["/tmp/retailops-dev.tfplan"]
    L -. cleanup .-> E1
```
