# RetailOps Cost Monitoring

**Project:** Cloud-Native RetailOps Platform
**Workstream:** FinOps / AWS Foundation
**Sprint:** Sprint 10 — Terraform and AWS Foundation
**Commit:** `docs(finops): add cost assumptions and cleanup strategy`

---

## 1. Purpose

This document defines how RetailOps should monitor cost during early AWS foundation work.

The goal is to make cost visible as soon as resources are introduced, instead of waiting until the end of the month or after an accidental always-on deployment.

---

## 2. Monitoring principle

RetailOps follows this cost-monitoring principle:

> Every cloud experiment should leave cost evidence, cleanup evidence, and a decision about whether anything should remain running.

This is especially important because Sprint 10 introduces AWS foundation components that may be applied for short validation sessions later.

---

## 3. What to monitor

### 3.1. Resource existence

After any real `terraform apply`, verify what exists.

Check:

- VPCs,
- subnets,
- route tables,
- internet gateways,
- security groups,
- IAM policies/roles,
- ECR repositories,
- ECR images,
- AWS Budgets,
- any resource tagged with `Project=retailops`.

### 3.2. Resource cost behavior

Review whether the resource can create idle cost.

| Resource type | Monitoring focus |
|---|---|
| VPC/subnets/route tables/security groups | Confirm no unexpected attached resources. |
| NAT Gateway | Must not appear unless explicitly approved. |
| ECR repositories | Check image count and storage growth after pushes. |
| IAM | Check permissions and avoid access keys. |
| AWS Budget | Confirm guardrail exists and notification posture is intentional. |
| CloudWatch logs | Check retention if future workloads send logs. |
| EKS/RDS/OpenSearch/MSK | Should not exist in early Sprint 10 unless separately approved. |

---

## 4. FinOps signals

Recommended cost signals:

| Signal | Meaning | Source |
|---|---|---|
| Estimated Monthly Cloud Cost | Expected monthly cost for planned AWS scope. | AWS Pricing Calculator / docs. |
| Idle Baseline Monthly Cloud Cost | Estimated cost with no users or traffic. | Pricing estimate + resource list. |
| Budget Limit | Dev cost guardrail. | Terraform output / AWS Budgets. |
| Budget Alert Status | Whether notification routing is enabled. | Terraform output / AWS Budgets. |
| Untagged Resource Count | Governance and cleanup risk. | Resource Groups Tagging API / console review. |
| ECR Image Count | Registry storage growth risk. | ECR repository review. |
| NAT Gateway Count | Idle networking cost risk. | Terraform plan / AWS Console. |
| Persistent Resource Count | Resources intentionally left after validation. | Tags and cleanup notes. |

---

## 5. Monitoring workflow

### 5.1. Before AWS apply

Run:

```bash
terraform -chdir=infra/environments/dev fmt -recursive
terraform -chdir=infra/environments/dev validate
terraform -chdir=infra/environments/dev plan \
  -var-file=terraform.tfvars.example \
  -no-color | tee ci-cd/reports/iac/terraform-plan-cost-review.txt
```

Review the plan for:

- number of resources to add/change/destroy,
- NAT Gateway or Elastic IP resources,
- EKS/RDS/OpenSearch/MSK resources,
- untagged resources,
- IAM permission scope,
- ECR repository and lifecycle policy settings,
- budget limit and notification posture.

### 5.2. During AWS validation

If a real apply is approved later, record:

- who ran the apply,
- when it started,
- target region,
- exact command,
- Terraform output,
- resources created,
- screenshots if used for portfolio evidence.

Recommended evidence path:

```text
docs/evidence/aws/
ci-cd/reports/iac/
```

### 5.3. After AWS validation

Immediately decide:

| Decision | Expected action |
|---|---|
| Keep temporarily | Document why, owner, review date, and estimated cost. |
| Keep persistently | Document why it must remain, cost expectation, and risk. |
| Destroy | Run cleanup runbook and collect evidence. |
| Pause | Stop/suspend supported resources where possible. |
| Defer | Remove or disable the resource from Terraform until needed. |

---

## 6. Cost review checklist

Before leaving any AWS resource active, check:

- [ ] Is the resource managed by Terraform?
- [ ] Does it have `Project`, `Environment`, `Owner`, `ManagedBy`, `CostCenter`, and `Lifecycle` tags where supported?
- [ ] Is it temporary or persistent?
- [ ] Is there a reason it must remain after validation?
- [ ] Is a budget guardrail in place?
- [ ] Are notifications configured without committing private data to the repository?
- [ ] Is NAT Gateway disabled unless explicitly approved?
- [ ] Are ECR lifecycle policies active?
- [ ] Are managed services such as EKS/RDS/OpenSearch/MSK absent unless approved?
- [ ] Is there a cleanup command or runbook path?

---

## 7. Suggested review cadence

| Situation | Cadence |
|---|---|
| Local-only MVP | Review during sprint closeout. |
| Plan-only Terraform work | Review every infrastructure commit. |
| Short-lived AWS validation | Review immediately before and after apply/destroy. |
| Persistent dev resources | Review weekly while active. |
| Production-like target environment | Review before creation, after creation, and during every release milestone. |

---

## 8. Alert levels

| Level | Example condition | Action |
|---|---|---|
| Green | Plan-only or local-only, no AWS resources active. | Continue. |
| Yellow | Temporary AWS resources active with documented owner and cleanup date. | Monitor and close out. |
| Orange | Persistent resources active without recent review. | Review and justify. |
| Red | Unexpected NAT Gateway, EKS, RDS, OpenSearch, MSK, or untagged resources. | Stop and remediate. |
| Critical | Unknown resource spend, secrets exposed, or private data committed. | Escalate, revoke, cleanup, and document incident. |

---

## 9. Evidence examples

Good cost evidence includes:

- Terraform plan saved to `ci-cd/reports/iac/`,
- screenshot of AWS Budget,
- screenshot or export of Cost Explorer after real apply,
- list of resources tagged `Project=retailops`,
- ECR repository image count,
- cleanup verification output,
- short note explaining why any resource remains active.

---

## 10. Senior DevOps review note

Cost monitoring is not only a finance activity.

For DevOps, cost monitoring is part of:

- operational readiness,
- architecture quality,
- release governance,
- incident prevention,
- and portfolio credibility.
