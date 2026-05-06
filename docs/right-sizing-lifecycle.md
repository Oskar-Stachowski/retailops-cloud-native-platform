# RetailOps Right-Sizing and Resource Lifecycle

**Project:** Cloud-Native RetailOps Platform  
**Workstream:** FinOps / AWS Foundation  
**Sprint:** Sprint 10 — Terraform and AWS Foundation  
**Commit:** `docs(finops): add cost assumptions and cleanup strategy`

---

## 1. Purpose

This document defines how RetailOps should decide whether AWS resources are appropriately sized and whether they should be temporary or persistent.

Right-sizing is not only about choosing a smaller instance type. It is about matching infrastructure to the current maturity stage of the platform.

---

## 2. Core principle

RetailOps follows this right-sizing principle:

> Start with the smallest useful architecture that proves the decision, then scale only when evidence requires it.

This protects the project from overengineering and unnecessary cloud spend while preserving a clear path toward production maturity.

---

## 3. Lifecycle categories

Every AWS resource should have a lifecycle intention.

| Lifecycle | Meaning | Expected behavior |
|---|---|---|
| Local-only | No AWS resource exists. | Preferred for MVP work. |
| Plan-only | Terraform can describe the resource, but it is not applied. | Good for review and architecture evidence. |
| Temporary | Resource may be created for validation, screenshots, or testing. | Destroy after evidence is collected. |
| Persistent-dev | Resource remains for repeated dev validation. | Requires documented reason and cost review. |
| Production-like | Resource supports a mature environment. | Requires stronger governance, monitoring, and approval. |

---

## 4. Default lifecycle by resource type

| Resource type | Default lifecycle during Sprint 10 | Reason |
|---|---|---|
| Terraform scaffold | Persistent in repository | Code and standards are project assets. |
| VPC baseline | Temporary if applied | Useful for validation, not required always-on. |
| Subnets and route tables | Temporary if applied | Part of VPC validation. |
| NAT Gateway | Disabled / not created | Avoid idle cost unless explicitly justified. |
| Security groups | Temporary if applied | Baseline evidence only. |
| IAM planning policy | Temporary or persistent-dev | Useful for future CI/CD plan checks, but permissions require review. |
| ECR repositories | Temporary or persistent-dev | Useful for release workflow evidence; storage must be controlled. |
| ECR lifecycle policy | Persistent with ECR | Prevents registry growth. |
| AWS Budget | Temporary or persistent-dev | Useful guardrail when AWS validation starts. |
| EKS/RDS/OpenSearch/MSK | Deferred | Target maturity, not early baseline. |

---

## 5. Right-sizing decision matrix

Before creating or keeping a resource, classify it.

| Question | If yes | If no |
|---|---|---|
| Does the resource prove current sprint value? | Consider temporary creation. | Keep plan-only or defer. |
| Can local tooling prove the same thing? | Prefer local. | Consider cloud validation. |
| Does the resource have idle cost? | Add stronger review and cleanup. | Still tag and monitor. |
| Is the resource needed across many validation sessions? | Consider persistent-dev. | Destroy after use. |
| Does it require broad IAM permissions? | Review least privilege first. | Continue with standard checks. |
| Does it contain or process sensitive data? | Do not use in MVP without security design. | Use synthetic data only. |
| Can it be recreated from Terraform? | Safe to destroy after evidence. | Document manual dependency before changes. |

---

## 6. Right-sizing by platform area

### 6.1. Networking

Current stance:

- VPC structure is useful as architecture foundation.
- Public/private subnet separation is valid for future EKS/RDS design.
- NAT Gateway is disabled until there is a justified private outbound requirement.

Right-sizing guidance:

- avoid multi-environment VPCs until dev baseline is proven,
- avoid NAT Gateway for demo-only private subnet layouts,
- avoid extra route tables and endpoints until a workload needs them,
- use simple CIDR assumptions and document them.

### 6.2. Compute

Current stance:

- local containers are enough for MVP.
- EKS is a target maturity component.

Right-sizing guidance:

- do not create EKS before release workflow and workload requirements are clear,
- prefer local Docker Compose until Kubernetes-specific evidence is needed,
- when Kubernetes is introduced, start with a minimal dev cluster and clear teardown policy.

### 6.3. Database

Current stance:

- local PostgreSQL is enough for current MVP evidence.
- RDS is deferred.

Right-sizing guidance:

- do not create RDS for static demo screenshots,
- use seed scripts and local data first,
- introduce RDS when cloud runtime requires persistent managed database behavior,
- use small dev settings and lifecycle tags.

### 6.4. Container registry

Current stance:

- ECR is useful for future release workflow.
- Image growth must be controlled.

Right-sizing guidance:

- keep repository count minimal,
- use immutable tags where appropriate,
- keep lifecycle policy active,
- review old images after release experiments,
- avoid pushing large experimental images repeatedly.

### 6.5. Observability

Current stance:

- MVP observability should start with health endpoints, logs, CI output, and local evidence.
- Managed observability stacks are deferred.

Right-sizing guidance:

- avoid long-retention logs before cloud runtime exists,
- avoid always-on monitoring stacks until workloads exist,
- treat Grafana/Prometheus screenshots as local evidence first where possible,
- introduce cloud observability when AWS workloads need runtime visibility.

### 6.6. MLOps

Current stance:

- local scripts and reports are enough for baseline ML evidence.
- managed ML services are target maturity.

Right-sizing guidance:

- prove data/model value before managed ML infrastructure,
- avoid expensive always-on notebooks or endpoints,
- version model evidence locally first,
- introduce managed inference only when needed for delivery evidence.

---

## 7. Cleanup expectation by lifecycle

| Lifecycle | Cleanup expectation |
|---|---|
| Local-only | No AWS cleanup required. |
| Plan-only | No AWS cleanup required, but clean generated local `.terraform` artifacts if needed. |
| Temporary | Destroy after validation and verify resources are gone. |
| Persistent-dev | Review regularly and document why it remains. |
| Production-like | Requires formal runbook, monitoring, and rollback/restore assumptions. |

---

## 8. Resource promotion policy

A resource may move from temporary to persistent-dev only when all are true:

- the resource supports repeated validation,
- Terraform can recreate it,
- tags are complete,
- estimated cost is understood,
- cleanup process is documented,
- owner is clear,
- security risk is reviewed,
- no private data or secrets are embedded.

A resource should not become persistent just because it is inconvenient to recreate.

---

## 9. Review questions for pull requests

Use these questions during infrastructure review:

1. What current capability does this resource enable?
2. Why is local-first not enough?
3. Is this plan-only, temporary, persistent-dev, or production-like?
4. What is the idle cost risk?
5. What is the cleanup path?
6. What tag proves lifecycle and ownership?
7. Does the plan introduce NAT Gateway, EKS, RDS, OpenSearch, MSK, or unmanaged compute?
8. Is the IAM scope justified?
9. Is the resource count minimal?
10. What evidence will prove the resource worked?

---

## 10. Senior DevOps review note

Right-sizing is a habit.

A junior engineer often asks: "Can we deploy this?"

A senior engineer also asks:

- "Should we deploy this now?"
- "How long should it live?"
- "Who owns it?"
- "How much does it cost while idle?"
- "How do we prove it is gone?"
