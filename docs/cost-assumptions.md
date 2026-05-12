# RetailOps Cost Assumptions

**Project:** Cloud-Native RetailOps Platform
**Workstream:** FinOps / AWS Foundation
**Sprint:** Sprint 10 — Terraform and AWS Foundation
**Commit:** `docs(finops): add cost assumptions and cleanup strategy`

---

## 1. Purpose

This document defines the cost assumptions used during Sprint 10.

The goal is not to create a perfect cloud bill estimate. The goal is to make cost boundaries explicit before AWS resources become part of the regular delivery workflow.

Senior DevOps principle:

> Cost is an architectural constraint, not an afterthought.

---

## 2. Current delivery stance

RetailOps currently follows a **local-first and cost-aware** approach.

The platform can be designed for AWS while still avoiding unnecessary always-on cloud infrastructure during early MVP work.

Current assumption:

| Area | Current stance |
|---|---|
| Local development | Default execution path. |
| Terraform | Safe planning and validation first. |
| AWS apply | Manual, deliberate, and evidence-driven only. |
| Production-like AWS | Target maturity, not early default. |
| Real business data | Not used. Synthetic/demo data only. |
| Budget posture | Conservative dev guardrails. |

---

## 3. Scope categories

RetailOps uses four cost-scope categories.

| Scope | Meaning | Cost expectation |
|---|---|---|
| Local MVP | Docker Compose, local API, frontend, local PostgreSQL, seed data. | No AWS runtime cost. |
| Plan-only AWS foundation | Terraform can validate and generate plans without applying resources. | No resources created by the plan itself. |
| Short-lived Dev AWS | Temporary resources used for validation screenshots, smoke checks, or portfolio evidence. | Create only when needed and destroy after evidence. |
| Target architecture | EKS, RDS, OpenSearch, MSK, managed ML, mature observability, multi-environment delivery. | Documented as future maturity, not always-on during Sprint 10. |

---

## 4. Sprint 10 Terraform cost assumptions

The current Sprint 10 Terraform baseline is intended as an AWS foundation, not as a full production runtime.

| Component | Current assumption | Cost risk |
|---|---|---|
| VPC | Baseline VPC with public/private subnet structure. | Low by itself, but attached resources may create cost later. |
| Public subnets | Prepared for future load balancers or controlled entry points. | Low by themselves. |
| Private subnets | Prepared for future workloads such as EKS/RDS. | Low by themselves. |
| NAT Gateway | Disabled intentionally for early cost control. | NAT Gateway would create idle cost if enabled. |
| Security groups | Baseline network boundaries only. | Low by themselves. |
| IAM baseline | Read-oriented Terraform planning policy; no access keys created. | Low direct cost, but high security impact if expanded carelessly. |
| ECR repositories | Prepared for backend/frontend images. | Storage cost may appear after pushing images. |
| ECR lifecycle policy | Keeps only a limited number of images. | Reduces image storage growth risk. |
| AWS Budget | Monthly guardrail for dev environment. | Requires review before real apply. |
| Notifications | Private notification emails are not committed to the repository. | Prevents leaking personal data. |

---

## 5. Cost assumptions by maturity phase

### 5.1. MVP phase

MVP should prioritize proving business and engineering value locally.

MVP should produce:

- local application runtime evidence,
- API health and readiness evidence,
- seed/demo data evidence,
- Docker Compose evidence,
- test and security scan evidence,
- Terraform format/validate/plan evidence.

MVP should not require:

- EKS,
- RDS,
- MSK,
- OpenSearch,
- managed ML platforms,
- NAT Gateway,
- multi-region architecture,
- long-retention cloud logs.

### 5.2. AWS foundation phase

AWS foundation exists to prove infrastructure readiness.

Acceptable work:

- Terraform module structure,
- safe VPC baseline,
- IAM planning baseline,
- ECR registry baseline,
- budget guardrail,
- cost and cleanup documentation.

Not acceptable by default:

- uncontrolled `terraform apply`,
- broad IAM permissions,
- unmanaged resources created manually in AWS Console,
- always-on managed services without evidence,
- private account identifiers in docs.

### 5.3. Target architecture phase

Target architecture may include managed AWS services once there is a reason.

A future service should be introduced only when at least one of these is true:

1. It proves a portfolio capability that cannot be shown locally.
2. It is required by a later Sprint deliverable.
3. It supports a security, reliability, or delivery gate.
4. It has a documented cost estimate and cleanup path.
5. It can be destroyed or suspended safely after validation.

---

## 6. Cost estimation boundaries

This repository should avoid pretending that estimates are real invoices.

Recommended language:

| Use | Avoid |
|---|---|
| Estimated monthly cloud cost | Guaranteed monthly cost |
| Plan-based resource estimate | Real production bill |
| Idle baseline assumption | Exact AWS invoice |
| Pricing Calculator evidence | Hand-wavy "cheap enough" statement |

Future cost estimates should be based on:

- Terraform plan resource list,
- AWS Pricing Calculator,
- AWS Billing / Cost Explorer after real apply,
- ECR image storage review,
- CloudWatch log retention review,
- resource tags and environment boundaries.

---

## 7. Idle baseline assumptions

Idle baseline cost means:

> The estimated monthly cloud cost when the platform exists but nobody is using it.

For RetailOps, idle baseline matters because this is a portfolio project. A platform that is technically impressive but expensive while idle is not a mature DevOps showcase.

Current idle baseline assumptions:

| Resource group | Sprint 10 expectation |
|---|---|
| Local runtime | No AWS idle cost. |
| Terraform plan-only | No AWS idle cost from planning alone. |
| VPC foundation after apply | Should remain minimal but must still be checked after creation. |
| NAT Gateway | Disabled; should remain disabled unless explicitly justified. |
| ECR | Storage grows only after image pushes; lifecycle policy should limit old images. |
| Budget | Guardrail resource; review before apply. |
| EKS/RDS/OpenSearch/MSK | Deferred; should not be part of idle Sprint 10 baseline. |

---

## 8. Decision rules before adding a new AWS service

Before adding any future AWS resource, answer these questions:

1. What business or platform capability does this resource prove?
2. Can the same evidence be produced locally?
3. Is this resource temporary or persistent?
4. What tag identifies owner, environment, cost center, and lifecycle?
5. What is the estimated idle monthly cost?
6. How will we verify that it was destroyed or cleaned up?
7. Does the Terraform plan show any expensive always-on dependency?
8. Does the change introduce data, secret, or access risk?
9. Is there a cheaper AWS-native alternative?
10. Is the cost acceptable for a portfolio learning environment?

---

## 9. Explicit deferred services

These services should remain target maturity unless a later task explicitly approves them:

| Service | Why deferred |
|---|---|
| Amazon EKS | Cluster cost and operational complexity are not needed for early MVP proof. |
| Amazon RDS | Local PostgreSQL is enough until cloud runtime requires managed persistence. |
| Amazon MSK | Streaming is target maturity; batch/seed data is enough for MVP. |
| OpenSearch Service | Valuable later, but too expensive and operationally heavy for early always-on use. |
| NAT Gateway | Useful for private subnet outbound access, but creates idle cost. |
| SageMaker / managed ML | ML maturity should follow baseline model evidence. |
| Long-retention CloudWatch logs | Useful after cloud workloads exist, not before. |

---

## 10. Evidence expected from this document

This document supports:

- cost-aware architecture review,
- Terraform plan review,
- AWS apply approval discussion,
- cleanup planning,
- portfolio explanation for recruiters,
- FinOps consistency with `docs/finops.md`,
- future AWS Pricing Calculator evidence.

---

## 11. Senior DevOps review note

A mature infrastructure project does not show maturity by turning on every managed service immediately.

It shows maturity by proving that every service has:

- a reason,
- an owner,
- a lifecycle,
- a cost boundary,
- a cleanup path,
- and evidence that it supports the platform.
