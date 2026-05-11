# AWS Foundation Architecture — Sprint 10

**Project:** RetailOps Cloud-Native Platform
**Sprint:** Sprint 10 — Terraform and AWS Foundation
**Commit:** `docs(aws): add AWS service inventory and foundation architecture`
**Scope:** Documentation / architecture / evidence

---

## 1. Purpose

This document describes the Sprint 10 AWS foundation architecture for RetailOps.

It is separate from the executive case study because it is a technical infrastructure document. The goal is to explain what the AWS foundation contains, what it intentionally avoids, and how Terraform modules map to future platform maturity.

---

## 2. Architecture stance

RetailOps follows a **local-first, AWS-ready** architecture path.

That means:

- the application MVP can run locally using Docker Compose,
- Terraform can define and validate AWS foundation resources,
- AWS resources are introduced gradually,
- expensive always-on services are deferred until justified,
- `terraform apply` is not automatic in Sprint 10,
- diagrams may show target architecture without implying immediate deployment.

---

## 3. Current Terraform module map

```text
infra/
├── environments/
│   └── dev/
│       └── main.tf
└── modules/
    ├── tags/
    ├── vpc/
    ├── iam/
    ├── ecr/
    ├── budget/
    └── cloudwatch/
```

The `dev` environment composes the modules. The modules keep stable infrastructure concerns isolated and reviewable.

Detailed module map:

```text
docs/diagrams/terraform-module-map.mmd
```

---

## 4. Layered AWS foundation

| Layer | Current Sprint 10 scope | Future maturity |
|---|---|---|
| Local MVP | Docker Compose, FastAPI, frontend, local PostgreSQL, synthetic data. | Remains the fastest development and demo path. |
| CI/CD validation | GitHub Actions and local make targets validate code, Terraform, and IaC security. | Jenkins can later own release-confidence orchestration. |
| Terraform composition | `infra/environments/dev` wires baseline modules. | Future environments may add staging/prod-like separation. |
| Network foundation | VPC, public/private subnets, route tables, IGW, security groups. | NAT, endpoints, ALB, EKS networking, RDS subnet groups. |
| Identity foundation | Read-oriented Terraform plan policy and guarded future trust patterns. | Separate apply/deploy roles, workload identity, permissions boundaries. |
| Registry foundation | ECR repositories and lifecycle policy. | Image publishing, provenance, SBOM, release promotion. |
| Cost foundation | AWS Budget baseline and tagging standards. | Cost Explorer evidence, budget alarms, policy gates, right-sizing reviews. |
| Observability foundation | CloudWatch log groups with short retention. | Metrics, dashboards, alarms, traces, SLO evidence. |

---

## 5. Current implemented foundation

The current Terraform foundation can represent:

- reusable tags,
- VPC and subnet layout,
- route table structure,
- application and database security groups,
- IAM plan/discovery policy,
- optional GitHub Actions and Jenkins trust patterns,
- ECR repositories and lifecycle policies,
- AWS Budget guardrail,
- CloudWatch log groups.

These components are sufficient to prove that the project understands AWS infrastructure foundations without prematurely creating a full production runtime.

---

## 6. Explicitly deferred architecture

The following are intentionally not part of the current foundation:

| Deferred item | Reason |
|---|---|
| EKS cluster | High operational scope; should follow container registry, IAM, networking, and cost decisions. |
| RDS PostgreSQL | Local PostgreSQL is enough for MVP; managed DB should come with backup, subnet, security, and cost decisions. |
| NAT Gateway | Avoid idle cost until private workloads require outbound internet. |
| OpenSearch | Expensive and operationally heavy for early Sprint 10. |
| MSK | Event streaming is future maturity, not foundation baseline. |
| Public ALB | No AWS-hosted application runtime yet. |
| Terraform remote state | Important future decision, but not required for local plan-only validation. |
| Apply/deploy IAM role | Requires separate approval and governance model. |

---

## 7. Architecture review rules

A future AWS change should be accepted only when it passes these review rules:

1. The service has a clear business, platform, or portfolio purpose.
2. The Terraform plan is understandable and reviewable.
3. Tags identify project, environment, owner, cost center, and lifecycle.
4. Cost assumptions and cleanup strategy are documented.
5. IAM permissions follow least privilege as far as the service supports it.
6. The change does not silently turn target architecture into always-on infrastructure.
7. The service can be destroyed or suspended after validation unless explicitly approved as persistent.

---

## 8. How this document should be used

Use this document when explaining Sprint 10 to a reviewer:

- `docs/aws-service-inventory.md` answers **what AWS services exist, are planned, or are deferred**.
- `docs/aws-architecture.md` answers **how the AWS foundation fits together**.
- `docs/diagrams/aws-foundation.png` gives a visual overview.
- `docs/diagrams/terraform-module-map.mmd` shows how the Terraform modules compose the baseline.
