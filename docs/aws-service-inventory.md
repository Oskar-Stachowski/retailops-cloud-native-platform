# AWS Service Inventory — Sprint 10 Foundation

**Project:** RetailOps Cloud-Native Platform  
**Sprint:** Sprint 10 — Terraform and AWS Foundation  
**Commit:** `docs(aws): add AWS service inventory and foundation architecture`  
**Scope:** Documentation / architecture / evidence

---

## 1. Purpose

This document defines the AWS service inventory for the Sprint 10 foundation.

The goal is to clearly separate:

- services represented in the current Terraform baseline,
- services that are planned for later delivery stages,
- services that are intentionally deferred because they would create unnecessary cost or complexity during the local-first MVP phase.

This inventory is intentionally conservative. It supports cloud-native architecture planning without implying that every target AWS service should be created immediately.

---

## 2. Service status legend

| Status | Meaning |
|---|---|
| `Implemented in Terraform` | Terraform code currently defines this service/module. |
| `Plan-only baseline` | The service can appear in Terraform plan, but apply is not automatic. |
| `Documented target` | The service belongs to the desired future architecture, but is not part of the current Sprint 10 baseline. |
| `Deferred` | The service is intentionally not created now because cost, operational maturity, or dependency requirements are not justified yet. |

---

## 3. Current Sprint 10 AWS foundation inventory

| AWS area | Service / capability | Current status | Terraform location | Purpose | Cost / risk note |
|---|---|---|---|---|---|
| Networking | Amazon VPC | Implemented in Terraform | `infra/modules/vpc` | Foundation network boundary for future AWS workloads. | Low direct cost; attached resources may create cost later. |
| Networking | Public subnets | Implemented in Terraform | `infra/modules/vpc` | Future load balancer or controlled public entry point placement. | Do not place application workloads directly in public subnets by default. |
| Networking | Private subnets | Implemented in Terraform | `infra/modules/vpc` | Future private app, EKS, RDS, or internal service placement. | No NAT Gateway by default, so outbound internet is intentionally limited. |
| Networking | Internet Gateway | Implemented in Terraform | `infra/modules/vpc` | Public route table target for future internet-facing entry points. | Review public exposure before real apply. |
| Networking | NAT Gateway | Deferred | Not created | Future private subnet egress option. | Intentionally disabled to avoid idle networking cost. |
| Security | Security groups | Implemented in Terraform | `infra/modules/vpc` | Baseline app/database traffic boundaries. | No public SSH/RDP/app ingress should be introduced without review. |
| Identity | IAM plan policy | Implemented in Terraform | `infra/modules/iam` | Read-oriented discovery policy for future Terraform plan validation. | Some read/list actions may require `Resource = "*"`; keep policy read-only. |
| Identity | GitHub Actions plan role | Optional / guarded baseline | `infra/modules/iam` | Future OIDC-based CI plan workflow. | Should remain disabled until trust inputs are explicit. |
| Identity | Jenkins plan role | Optional / guarded baseline | `infra/modules/iam` | Future release-confidence plan role. | Requires explicit trusted AWS principal ARNs. |
| Identity | Apply / deploy role | Deferred | Not created | Future controlled deployment role. | Requires separate ADR, approval, and tighter governance. |
| Registry | Amazon ECR repositories | Implemented in Terraform | `infra/modules/ecr` | Container registry baseline for API and frontend images. | Storage cost appears after image pushes; lifecycle policy should limit growth. |
| Registry | ECR lifecycle policy | Implemented in Terraform | `infra/modules/ecr` | Limit old image accumulation. | Supports cost control and cleanup discipline. |
| Cost | AWS Budgets | Implemented in Terraform | `infra/modules/budget` | Dev budget guardrail before real AWS validation. | Notification emails should not be committed to the repository. |
| Observability | CloudWatch Log Groups | Implemented in Terraform | `infra/modules/cloudwatch` | Minimal AWS-native logging foundation. | Short retention by default to avoid unnecessary log storage cost. |
| Governance | Tags | Implemented in Terraform | `infra/modules/tags` | Consistent Project, Environment, Owner, ManagedBy, CostCenter, Lifecycle metadata. | Tags must not contain secrets or personal/private identifiers. |

---

## 4. Documented target services

These services are important for the long-term cloud-native story, but they are not part of the current Sprint 10 always-on baseline.

| Target area | Future AWS service | Intended future role | Current Sprint 10 stance |
|---|---|---|---|
| Runtime | Amazon EKS | Kubernetes runtime for production-style workloads. | Target architecture only. |
| Database | Amazon RDS for PostgreSQL | Managed relational database for application data. | Deferred; local PostgreSQL remains MVP default. |
| Object storage | Amazon S3 | Artifacts, data lake inputs, reports, Terraform remote state candidate. | Documented target; remote state decision is separate. |
| NoSQL / state | Amazon DynamoDB | Potential locking/state or operational metadata use case. | Documented target; not required yet. |
| Observability | CloudWatch metrics, alarms, dashboards | Production-style operational visibility. | Future maturity beyond log group baseline. |
| Networking | VPC endpoints | Private AWS service access and possible NAT cost reduction. | Future networking decision. |
| Delivery | ECR publishing from Jenkins/GitHub Actions | Release candidate image workflow. | Future CI/CD maturity. |
| Eventing | EventBridge / MSK | Event-driven workflow and streaming architecture. | Future maturity only. |
| Search | OpenSearch | Search/analytics use cases. | Deferred due to cost and operational weight. |
| ML/MLOps | SageMaker or equivalent | Future model training/serving workflow. | Future MLOps sprint, not Sprint 10 baseline. |

---

## 5. Implemented vs target architecture boundary

### Implemented now

Sprint 10 currently focuses on foundation capabilities:

- Terraform environment and reusable module layout,
- naming and tagging standards,
- VPC baseline,
- IAM planning baseline,
- ECR repository baseline,
- budget guardrail,
- CloudWatch log group baseline,
- validation and IaC security scanning workflows,
- architecture and governance documentation.

### Not implemented now

The current scope intentionally does not create:

- EKS cluster,
- RDS database,
- NAT Gateway,
- OpenSearch domain,
- MSK cluster,
- production-grade CloudWatch dashboards and alarms,
- public application load balancer,
- apply/deploy IAM role,
- remote Terraform state backend.

These are future decisions, not missing Sprint 10 work.
