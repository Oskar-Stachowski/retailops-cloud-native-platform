# AWS Cleanup Runbook

**Project:** Cloud-Native RetailOps Platform  
**Workstream:** FinOps / AWS Foundation  
**Sprint:** Sprint 10 — Terraform and AWS Foundation  
**Commit:** `docs(finops): add cost assumptions and cleanup strategy`

---

## 1. Purpose

This runbook explains how to clean up temporary AWS resources created for RetailOps validation.

Use this runbook after any approved AWS experiment, especially after Terraform `apply` in a dev environment.

---

## 2. Safety warning

Do not run destructive commands blindly.

Before cleanup, confirm:

- correct AWS account,
- correct AWS region,
- correct Terraform workspace/environment,
- correct branch,
- correct `terraform.tfvars` file,
- current Terraform state is available,
- no required resource should remain active.

Senior DevOps rule:

> Cleanup is part of delivery. If we cannot safely destroy it, we did not understand what we created.

---

## 3. Current Sprint 10 cleanup scope

The current Sprint 10 foundation may include these Terraform-managed resource groups if applied:

| Resource group | Expected cleanup behavior |
|---|---|
| AWS Budget | Remove if the dev validation environment is no longer used. |
| ECR repositories | Remove if image evidence is no longer needed; otherwise document persistent-dev reason. |
| ECR lifecycle policies | Removed with ECR repository cleanup. |
| IAM planning policy | Remove if no CI/CD AWS plan validation needs it yet. |
| VPC | Remove after networking evidence is collected. |
| Subnets | Removed with VPC cleanup. |
| Route tables | Removed with VPC cleanup. |
| Internet Gateway | Removed with VPC cleanup. |
| Security groups | Removed with VPC cleanup. |

The Sprint 10 baseline should not create NAT Gateway, EKS, RDS, OpenSearch, MSK, or production-like always-on resources unless separately approved later.

---

## 4. Pre-cleanup checklist

Complete this checklist before destroying anything:

- [ ] I know which AWS account is active.
- [ ] I know which region is active.
- [ ] I know whether resources were created by Terraform.
- [ ] I have saved Terraform plan/apply evidence if needed.
- [ ] I have checked whether any ECR image evidence must be kept.
- [ ] I have checked whether any budget guardrail should remain.
- [ ] I have checked whether any resource is intentionally persistent.
- [ ] I have confirmed there are no real production users or workloads.
- [ ] I have reviewed the destroy plan before running destroy.
- [ ] I have a post-cleanup verification plan.

---

## 5. Identify current AWS identity

If AWS CLI is configured, run:

```bash
aws sts get-caller-identity
aws configure get region
```

Expected review:

- Account should be your intended learning/dev account.
- Region should match the Terraform environment, for example `eu-central-1`.
- Do not paste real account IDs into public docs or screenshots unless intentionally redacted.

---

## 6. Save a destroy plan first

From repository root:

```bash
terraform -chdir=infra/environments/dev plan \
  -destroy \
  -var-file=terraform.tfvars.example \
  -no-color | tee ci-cd/reports/iac/terraform-destroy-plan-sprint10.txt
```

Review the output before continuing.

The destroy plan should show only resources that belong to the intended dev foundation.

Stop if the plan includes unexpected resources.

---

## 7. Optional tagged resource discovery

If AWS CLI permissions allow it, list tagged resources:

```bash
aws resourcegroupstaggingapi get-resources \
  --tag-filters Key=Project,Values=retailops Key=Environment,Values=dev \
  --region eu-central-1
```

Review for:

- resources outside Terraform expectation,
- missing tags,
- resources that should not exist,
- resources that look production-like.

---

## 8. Check specific resource groups

### 8.1. VPC and networking

```bash
aws ec2 describe-vpcs \
  --filters "Name=tag:Project,Values=retailops" "Name=tag:Environment,Values=dev" \
  --region eu-central-1

aws ec2 describe-subnets \
  --filters "Name=tag:Project,Values=retailops" "Name=tag:Environment,Values=dev" \
  --region eu-central-1

aws ec2 describe-internet-gateways \
  --filters "Name=tag:Project,Values=retailops" \
  --region eu-central-1

aws ec2 describe-nat-gateways \
  --filter "Name=tag:Project,Values=retailops" \
  --region eu-central-1
```

Expected Sprint 10 result:

- VPC/subnets may exist only if applied.
- NAT Gateway should not exist.

### 8.2. ECR

```bash
aws ecr describe-repositories \
  --region eu-central-1

aws ecr list-images \
  --repository-name retailops-dev-api \
  --region eu-central-1

aws ecr list-images \
  --repository-name retailops-dev-frontend \
  --region eu-central-1
```

Review:

- whether repositories exist,
- whether image evidence must be kept,
- whether lifecycle policy is enough,
- whether repositories should be destroyed.

### 8.3. IAM

```bash
aws iam list-policies \
  --scope Local \
  --query "Policies[?contains(PolicyName, 'retailops')]"
```

Review:

- policy names,
- whether access keys were created manually,
- whether any role/user attachment exists unexpectedly.

### 8.4. Budgets

```bash
aws budgets describe-budgets \
  --account-id <AWS_ACCOUNT_ID>
```

Do not commit the real account ID to the repository.

Review:

- budget name,
- budget limit,
- notification configuration,
- whether private notification data is present outside the repository only.

---

## 9. Destroy Terraform-managed resources

Only after reviewing the destroy plan, run:

```bash
terraform -chdir=infra/environments/dev destroy \
  -var-file=terraform.tfvars.example
```

For portfolio-safe evidence, also save the final output if appropriate:

```bash
terraform -chdir=infra/environments/dev destroy \
  -var-file=terraform.tfvars.example \
  -no-color | tee ci-cd/reports/iac/terraform-destroy-sprint10.txt
```

Stop if Terraform asks to destroy resources you do not recognize.

---

## 10. Post-cleanup verification

After destroy, verify:

```bash
terraform -chdir=infra/environments/dev plan \
  -var-file=terraform.tfvars.example \
  -no-color | tee ci-cd/reports/iac/terraform-plan-after-cleanup-sprint10.txt
```

Expected result:

- If configuration still exists, Terraform may show resources that would be created again.
- That is normal.
- What matters is that previously created AWS resources are no longer active unless intentionally kept.

Also verify with AWS CLI:

```bash
aws resourcegroupstaggingapi get-resources \
  --tag-filters Key=Project,Values=retailops Key=Environment,Values=dev \
  --region eu-central-1
```

Expected result:

- no unexpected active resources,
- no NAT Gateway,
- no unreviewed ECR images,
- no unreviewed IAM policies,
- no unknown persistent resources.

---

## 11. 24-hour billing follow-up

Some billing views are delayed.

After a real AWS experiment:

- check Billing / Cost Explorer after the next billing data refresh,
- confirm no unexpected cost trend,
- confirm no always-on managed service remains,
- update cost evidence if needed.

---

## 12. Cleanup evidence template

Use this template in `docs/evidence/sprint-10/` if needed.

```markdown
# AWS Cleanup Evidence — Sprint 10

Date:

Operator:

AWS region:

Terraform environment:

Resources intentionally destroyed:

Resources intentionally kept:

Reason for keeping any resource:

Commands run:

Evidence files:

Follow-up required:

Senior review note:
```

---

## 13. Common mistakes

Avoid these mistakes:

- running `terraform destroy` in the wrong environment,
- assuming the plan and the real account are the same thing,
- forgetting ECR images,
- leaving NAT Gateway active after a demo,
- leaving RDS/EKS/OpenSearch/MSK active after testing,
- committing private notification emails,
- committing real account IDs,
- deleting resources that are not managed by this project,
- failing to collect evidence before cleanup.

---

## 14. Senior DevOps review note

A good cleanup runbook protects both cost and confidence.

It proves that the team can:

- create infrastructure intentionally,
- observe it,
- explain it,
- destroy it,
- and verify that no hidden cost remains.
