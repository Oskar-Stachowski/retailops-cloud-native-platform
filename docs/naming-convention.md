# RetailOps AWS Naming Convention

**Project:** Cloud-Native RetailOps Platform  
**Workstream:** Infrastructure / AWS Foundation  
**Sprint:** Sprint 10 — Terraform and AWS Foundation  
**Commit:** `docs(infra): add AWS naming and tagging standards`

---

## 1. Purpose

This document defines the naming convention for future AWS resources managed by Terraform in the RetailOps Platform.

The goal is to create predictable, readable, cost-aware, and reviewable infrastructure names before any real AWS resources are created.

At this stage, the project is still local-first. These standards prepare the AWS foundation, but they do not require `terraform apply` or the creation of real AWS services.

---

## 2. Naming principle

Every AWS resource name should answer four questions:

```text
Which project does this belong to?
Which environment does this belong to?
Which platform component does this support?
What type of resource is it?
```

Standard pattern:

```text
<project>-<environment>-<component>-<resource-type>
```

Example:

```text
retailops-dev-api-ecr
```

Meaning:

| Segment | Value | Meaning |
|---|---|---|
| `project` | `retailops` | Resource belongs to RetailOps. |
| `environment` | `dev` | Resource belongs to the development environment. |
| `component` | `api` | Resource supports the backend API component. |
| `resource-type` | `ecr` | Resource is an Elastic Container Registry repository. |

---

## 3. Terraform alignment

Commit 1 introduced a Terraform naming foundation in `infra/locals.tf`:

```hcl
name_prefix = "${local.normalized_project_name}-${var.environment}"
```

This means the base prefix is:

```text
<project>-<environment>
```

Future resources should extend that prefix with component and resource type:

```hcl
name = "${local.name_prefix}-api-ecr"
```

Result:

```text
retailops-dev-api-ecr
```

This keeps Terraform code simple while still enforcing the full naming convention.

---

## 4. Segment definitions

### 4.1. Project

Recommended value:

```text
retailops
```

Rules:

- use lowercase,
- keep it short,
- avoid spaces,
- avoid personal names,
- avoid company names that are not part of the project,
- keep the value stable across environments.

Terraform variable:

```hcl
project_name = "retailops"
```

---

### 4.2. Environment

Allowed values for this project:

```text
dev
staging
prod
```

Current Sprint 10 scope uses only:

```text
dev
```

Environment meaning:

| Environment | Purpose | Cost expectation |
|---|---|---|
| `dev` | Local-first and short-lived AWS validation. | Lowest cost, temporary by default. |
| `staging` | Future production-like validation. | Introduced only when platform maturity justifies it. |
| `prod` | Future production-like target. | Not part of early portfolio MVP. |

---

### 4.3. Component

The component explains which logical part of the platform the resource supports.

Recommended component values:

| Component | Meaning |
|---|---|
| `network` | VPC, subnets, route tables, gateways. |
| `iam` | IAM roles, policies, service identities. |
| `api` | Backend API infrastructure. |
| `frontend` | Frontend hosting or delivery resources. |
| `db` | Database-related resources. |
| `ecr` | Container registry resources when grouped separately. |
| `eks` | Kubernetes control plane or cluster resources. |
| `observability` | Logs, metrics, dashboards, alerting. |
| `security` | Security tooling, scanning, policy, runtime detection. |
| `ml` | ML/MLOps workloads, model artifacts, inference. |
| `data` | Data storage, ingestion, batch, event processing. |
| `platform` | Shared platform foundation resources. |

Use the most specific component that improves ownership and cost understanding.

---

### 4.4. Resource type

The resource type describes the AWS service or infrastructure object.

Examples:

| Resource type | Example use |
|---|---|
| `vpc` | Virtual Private Cloud. |
| `subnet` | Subnet. |
| `sg` | Security group. |
| `role` | IAM role. |
| `policy` | IAM policy. |
| `ecr` | ECR repository. |
| `eks` | EKS cluster. |
| `rds` | RDS database. |
| `s3` | S3 bucket. |
| `log-group` | CloudWatch log group. |
| `dashboard` | Monitoring dashboard. |
| `alarm` | CloudWatch or monitoring alarm. |

Keep resource type names understandable rather than overly compressed.

---

## 5. Examples

| Future resource | Example name |
|---|---|
| API container registry | `retailops-dev-api-ecr` |
| Frontend container registry | `retailops-dev-frontend-ecr` |
| Main VPC | `retailops-dev-network-vpc` |
| Public subnet | `retailops-dev-network-public-subnet` |
| API security group | `retailops-dev-api-sg` |
| EKS cluster | `retailops-dev-eks-cluster` |
| RDS database | `retailops-dev-db-rds` |
| API log group | `retailops-dev-api-log-group` |
| ML artifact bucket | `retailops-dev-ml-s3` |
| Shared platform role | `retailops-dev-platform-role` |

These names are examples only. They do not prove that the resources already exist.

---

## 6. Temporary vs persistent resources

Resource names should remain clear about ownership even when the resource is temporary.

The lifecycle intent belongs primarily in tags, not necessarily in the resource name.

Preferred:

```text
retailops-dev-api-ecr
```

With tag:

```text
Lifecycle = temporary
```

Avoid:

```text
retailops-dev-api-ecr-temp-delete-later
```

Reason: lifecycle may change, but resource identity should remain stable and readable.

---

## 7. When AWS naming rules differ

Some AWS services have strict naming rules.

Examples:

- S3 bucket names must be globally unique.
- Some names have length limits.
- Some services do not support uppercase characters.
- Some services do not support underscores.
- Some resources do not use a direct `name` field and rely on tags instead.

When a service requires a modified name, keep the standard as close as possible and document the deviation in the Terraform module or resource comment.

Example for future S3 bucket naming:

```text
retailops-dev-data-artifacts-<short-suffix>
```

Do not use real AWS account IDs, private identifiers, or secrets as suffixes.

---

## 8. Anti-patterns

Avoid names like:

```text
test
my-vpc
oskar-vpc
retailops-final
terraform-test-2
prod-new-final
aws-demo-resource
```

Why they are weak:

- unclear ownership,
- unclear environment,
- unclear purpose,
- difficult cost allocation,
- hard to review in Terraform plan,
- hard to clean up safely.

---

## 9. Review checklist

Before adding a future AWS resource, verify:

- name follows `<project>-<environment>-<component>-<resource-type>`,
- name is lowercase,
- name is understandable in a Terraform plan,
- component ownership is clear,
- environment is explicit,
- no personal or private identifiers are embedded,
- any AWS-service-specific exception is documented,
- matching tags are applied through `local.common_tags`.
