# Infrastructure

This directory contains Infrastructure as Code assets for the RetailOps Platform.

Sprint 10 starts with a local-first Terraform scaffold. The goal of the first commit is to prepare structure, standards, naming, tags, validation commands, and safe environment separation before any real AWS services are created.

## Commit 1 scope

This commit intentionally includes only Terraform foundation files:

- reusable foundation scaffold in `infra/`,
- development environment entry point in `infra/environments/dev/`,
- remote-state example in `backend.tf.example`,
- local Terraform validation targets in the root `Makefile`,
- IaC evidence and report folders.

## Explicitly out of scope for Commit 1

The following items are intentionally not introduced yet:

- no `terraform apply`,
- no VPC, IAM, ECR, EKS, RDS, S3, CloudWatch, or other AWS resources,
- no real remote backend values,
- no Terraform GitHub Actions workflow,
- no production module implementation.

## Directory layout

```text
infra/
├── .gitignore
├── README.md
├── backend.tf.example
├── environments
│   └── dev
│       ├── main.tf
│       └── terraform.tfvars.example
├── locals.tf
├── modules
│   └── README.md
├── outputs.tf
├── providers.tf
├── variables.tf
└── versions.tf
```

## Local validation

Run from the repository root:

```bash
terraform -chdir=infra/environments/dev fmt -recursive
terraform -chdir=infra/environments/dev init -backend=false
terraform -chdir=infra/environments/dev validate
```

Or use the root `Makefile`:

```bash
make terraform-fmt
make terraform-init
make terraform-validate
make terraform-check
```

## State management policy

Commit 1 uses local initialization with `-backend=false`. This prevents accidental remote backend usage before a real S3/DynamoDB state design exists.

`backend.tf.example` is only a template. Do not copy it to `backend.tf` until the AWS account, S3 state bucket, DynamoDB lock table, encryption, naming, and access model are intentionally designed.

## Cost and security policy

This infrastructure layer follows the RetailOps local-first FinOps strategy:

- validate infrastructure code before creating infrastructure,
- avoid always-on AWS resources during early MVP work,
- keep tags ready before resources exist,
- never commit real secrets, credentials, state files, or private `.tfvars` files.
