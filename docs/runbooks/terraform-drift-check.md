# Terraform Drift Check Runbook

**Project:** Cloud-Native RetailOps Platform
**Workstream:** Terraform / AWS Foundation / Operations
**Sprint:** Sprint 10 — Terraform and AWS Foundation
**Commit:** `docs(runbook): add Terraform drift and failed plan runbooks`

---

## 1. Purpose

This runbook explains how to check whether the real AWS environment has drifted away from the Terraform configuration and state.

Use it when:

- Terraform-managed resources may have been changed manually in AWS,
- a plan shows unexpected changes,
- CI reports a plan difference,
- local Terraform output does not match the expected Sprint 10 baseline,
- a reviewer asks whether the infrastructure is still aligned with code.

Senior DevOps rule:

> Drift is not automatically a bug, but unmanaged drift is always operational risk.

---

## 2. Important Sprint 10 note

Sprint 10 is primarily a foundation and validation sprint.

A drift check is meaningful only after resources were actually created and Terraform state exists.

If the environment has never been applied, `terraform plan` showing resources to create is expected. That is not drift. It means Terraform is comparing configuration against an empty state.

---

## 3. What counts as drift

| Situation | Interpretation |
|---|---|
| `terraform plan` returns no changes | Configuration, state, and remote resources are aligned. |
| `terraform plan` wants to update/delete resources that should already match code | Possible drift or intentional code change. |
| `terraform plan` wants to recreate resources after manual AWS edits | Likely drift. |
| `terraform plan` wants to create all resources in a never-applied environment | Not drift; expected plan-only baseline behavior. |
| Terraform cannot read state | State/backend problem, not a drift conclusion. |
| Terraform cannot authenticate to AWS | Credential problem, not a drift conclusion. |

---

## 4. Pre-check checklist

Before running a drift check, confirm:

- [ ] You are on the intended branch.
- [ ] Your working tree is clean or the local changes are intentional.
- [ ] You know whether the dev environment has ever been applied.
- [ ] You know which `terraform.tfvars` file should be used.
- [ ] AWS credentials are available only if checking real remote resources.
- [ ] You will not run `terraform apply` as part of this check.
- [ ] Any saved output will not expose secrets, real account IDs, or private identifiers.

---

## 5. Local static validation first

From the repository root:

```bash
terraform -chdir=infra/environments/dev fmt -recursive -check -diff
terraform -chdir=infra/environments/dev init -backend=false -input=false
terraform -chdir=infra/environments/dev validate
```

Expected result:

- formatting check passes,
- provider plugins initialize,
- configuration is valid.

If these commands fail, stop and use `docs/runbooks/terraform-failed-plan.md` before diagnosing drift.

---

## 6. Save a drift plan

Create a report directory if needed:

```bash
mkdir -p ci-cd/reports/iac
```

Run a plan with `-detailed-exitcode` and save output:

```bash
terraform -chdir=infra/environments/dev plan \
  -detailed-exitcode \
  -var-file=terraform.tfvars.example \
  -no-color \
  > ci-cd/reports/iac/terraform-drift-check.txt

DRIFT_EXIT_CODE=$?
cat ci-cd/reports/iac/terraform-drift-check.txt
printf "Terraform detailed exit code: %s\n" "$DRIFT_EXIT_CODE"
```

Exit code meaning:

| Exit code | Meaning | Action |
|---|---|---|
| `0` | No changes. | Environment is aligned with state and config. |
| `1` | Error. | Treat as failed plan, not drift. |
| `2` | Changes present. | Review whether the changes are expected or drift. |

---

## 7. Optional binary plan for deeper review

Use this only when you need a stable plan artifact for review.

```bash
terraform -chdir=infra/environments/dev plan \
  -detailed-exitcode \
  -var-file=terraform.tfvars.example \
  -out=tfplan \
  -no-color \
  > ci-cd/reports/iac/terraform-drift-check-summary.txt

terraform -chdir=infra/environments/dev show \
  -no-color tfplan \
  > ci-cd/reports/iac/terraform-drift-check-readable.txt
```

Do not commit binary plan files unless the team explicitly decides that they are safe and useful. Prefer committing the readable text report after review and redaction.

---

## 8. Review checklist for Sprint 10 resources

When the plan shows changes, review these resource groups:

| Resource group | Drift questions |
|---|---|
| VPC | Did CIDR, DNS support, or tags change outside Terraform? |
| Public subnets | Did route table association, public IP behavior, or tags change? |
| Private subnets | Did CIDR, route tables, or tags change? |
| Security groups | Did ingress/egress rules change manually? |
| IAM | Were policies, trust policies, or role attachments changed manually? |
| ECR | Were scan settings, lifecycle policy, tag mutability, or repositories changed manually? |
| AWS Budget | Was the limit, notification, or budget name changed manually? |
| CloudWatch log groups | Was retention changed manually? |

---

## 9. Classify the result

Use this table before taking action:

| Plan result | Classification | Next step |
|---|---|---|
| Only expected new resources in a never-applied environment | Expected baseline plan | Save plan evidence if needed. Do not call it drift. |
| Tags changed manually | Low/medium drift | Prefer restoring tags through Terraform. |
| Security group rule changed manually | Security-sensitive drift | Stop and review before applying. |
| IAM policy widened manually | Critical drift | Stop, review immediately, and document remediation. |
| Cost-related resource added manually | FinOps drift | Review cost impact and cleanup. |
| Terraform wants to destroy an unknown resource | High risk | Stop; verify state and ownership. |

---

## 10. Recommended response to drift

Do not immediately run `terraform apply`.

Recommended order:

1. Save the plan output.
2. Identify whether the change comes from code, state, or manual AWS edits.
3. Check commit history for intentional Terraform changes.
4. Check AWS console or AWS CLI only if needed.
5. Decide whether to:
   - accept the code change,
   - revert the manual AWS change,
   - import an intentionally created resource,
   - remove an unexpected resource,
   - update documentation or ADRs.
6. Get review before any destructive action.

---

## 11. Optional AWS CLI discovery

Use tagged resource discovery when AWS credentials are available:

```bash
aws resourcegroupstaggingapi get-resources \
  --tag-filters Key=Project,Values=retailops Key=Environment,Values=dev \
  --region eu-central-1
```

Review for:

- resources without expected tags,
- resources outside Terraform scope,
- resources that should not exist in Sprint 10,
- always-on services that may create cost.

Do not commit real account IDs or private identifiers from AWS CLI output.

---

## 12. Evidence template

Use this template when documenting a drift review.

```markdown
# Terraform Drift Check Evidence — Sprint 10

Date:
Operator:
Branch:
Terraform environment: infra/environments/dev
AWS region:
State available: yes/no
Resources previously applied: yes/no/unknown

Command run:

Exit code:

Result classification:
- no changes / expected baseline plan / possible drift / failed plan

Unexpected changes:

Security impact:

Cost impact:

Decision:

Follow-up actions:

Reviewer note:
```
