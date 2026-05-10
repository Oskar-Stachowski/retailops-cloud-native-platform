# RetailOps Infrastructure

This directory contains the Terraform foundation for the RetailOps AWS platform. Sprint 10 establishes a small, reviewable dev baseline that demonstrates cloud readiness without introducing permanent production workloads or unmanaged cost.

The current infrastructure scope is intentionally limited to foundational AWS services:

- shared naming and governance tags,
- dev VPC with public and private subnet layout,
- baseline security groups,
- read-only Terraform plan IAM policy and optional CI/CD assume-role wiring,
- ECR repositories for API and frontend images,
- monthly AWS Budget guardrail,
- CloudWatch log groups with short dev retention.

The Terraform code is designed for safe local validation and controlled showcase evidence. Routine CI does not run `terraform apply` or `terraform destroy`.

## Directory layout

```text
infra/
├── backend.tf.example
├── environments/
│   └── dev/
│       ├── main.tf
│       └── terraform.tfvars.example
├── modules/
│   ├── budget/
│   ├── cloudwatch/
│   ├── ecr/
│   ├── iam/
│   ├── tags/
│   └── vpc/
├── locals.tf
├── outputs.tf
├── providers.tf
├── variables.tf
└── versions.tf
```

## Environment

`infra/environments/dev` is the only active environment entry point in Sprint 10. It composes the reusable modules and keeps dev-specific defaults close to the plan command.

Run Terraform through the root `Makefile` targets or with explicit
`-chdir=infra/environments/dev`. The `infra/` root is not an environment entry
point.

The dev baseline is cost-aware by design:

- no NAT Gateway,
- no EKS cluster,
- no RDS database,
- no load balancer,
- no permanent compute workload,
- short CloudWatch log retention,
- ECR lifecycle policies,
- monthly budget guardrail.

Future `staging` or `prod` environments should be added only when the deployment model, remote state, approval flow, and cost controls are intentionally designed.

## Modules

| Module | Purpose |
|---|---|
| `modules/tags` | Produces the shared name prefix and mandatory governance/FinOps tags. |
| `modules/vpc` | Creates the VPC, public/private subnets, route tables, internet gateway, and baseline app/database security groups. |
| `modules/iam` | Creates a read-only Terraform plan policy and optional GitHub Actions/Jenkins plan roles. |
| `modules/ecr` | Creates API and frontend ECR repositories with immutable tags, scan-on-push, AES256 encryption, and lifecycle retention. |
| `modules/budget` | Creates the monthly AWS Budget guardrail, with private notification addresses kept out of committed examples. |
| `modules/cloudwatch` | Creates baseline CloudWatch log groups with configurable retention and optional KMS key input. |

## Local validation

Run from the repository root:

```bash
make terraform-fmt-check
make terraform-validate
make iac-scan
```

`make iac-scan` runs Terraform formatting checks, local initialization with backend disabled, validation, critical IAM/secret guardrails, TFLint, and Checkov report generation.

Create a dev plan only when safe AWS credentials are intentionally available:

```bash
make terraform-plan-dev
```

Do not run `terraform apply` or `terraform destroy` as part of routine local validation or CI. Those commands are reserved for a short, controlled showcase window with evidence capture and cleanup.

## CI/CD

Terraform validation is wired through `.github/workflows/terraform-plan.yml`.

The default CI path runs:

- Terraform setup,
- `make terraform-fmt-check`,
- `make terraform-validate`,
- validation evidence upload.

The optional dev plan job is manual-only through `workflow_dispatch`. It uses GitHub OIDC and a repository variable named `AWS_TERRAFORM_PLAN_ROLE_ARN` to assume a plan-only AWS role. The workflow does not contain static AWS credentials and does not run `terraform apply`.

IaC security checks are handled separately by `.github/workflows/iac-security.yml`, using TFLint and Checkov. Checkov is report-only in Sprint 10; critical blockers are enforced through explicit guardrails.

## State and artifacts

Sprint 10 uses local Terraform initialization with:

```bash
terraform -chdir=infra/environments/dev init -backend=false -input=false
```

`backend.tf.example` is only a template for a future S3/DynamoDB remote state design. Do not rename or copy it to `backend.tf` until state ownership, locking, encryption, naming, and access controls are approved.

Do not commit Terraform local artifacts:

- `.terraform/`
- `terraform.tfstate`
- `terraform.tfstate.backup`
- binary plan files such as `tfplan` or `*.tfplan`
- crash logs
- override files
- private `.tfvars` files

Commit only safe examples such as `terraform.tfvars.example` and provider lock files when intentionally generated.

## Security posture

The Sprint 10 foundation favors explicit controls over flexible but unsafe toggles:

- ECR image tags are immutable.
- ECR scan-on-push is enforced.
- IAM access keys and IAM users are not created.
- AdministratorAccess is not attached.
- Terraform plan permissions are read-only.
- Budget notification email addresses are sensitive inputs and are not committed.
- Public subnet auto-assign public IPv4 is disabled.
- Database security group ingress is limited to the application security group.

The Terraform plan IAM policy intentionally uses broad read/list/describe discovery permissions where AWS does not support useful resource-level scoping. This exception is documented and should eventually move into formal policy-as-code exception management.

## Evidence

Sprint 10 showcase evidence is stored under:

```text
docs/evidence/sprint-10/
```

That folder contains validation output, plan/apply/destroy evidence, sanitized console screenshots, Terraform outputs, and cleanup confirmation. Evidence should prove the baseline can be created and destroyed cleanly without leaving cost-generating resources behind.

## Future improvements

Recommended next steps:

- design remote state with S3, DynamoDB locking, KMS encryption, versioning, and least-privilege access,
- add scheduled drift detection with plan-only credentials,
- promote selected Checkov findings from report-only to hard gates,
- add VPC Flow Logs and stronger observability controls,
- add `terraform test` or Terratest module contract checks,
- publish signed container images to ECR with SBOM/provenance evidence,
- split future environments only when delivery and approval boundaries justify them.
