# RetailOps AWS Tagging Strategy

**Project:** Cloud-Native RetailOps Platform  
**Workstream:** Infrastructure / AWS Foundation  
**Sprint:** Sprint 10 — Terraform and AWS Foundation  
**Commit:** `docs(infra): add AWS naming and tagging standards`

---

## 1. Purpose

This document defines the AWS tagging strategy for future RetailOps infrastructure managed by Terraform.

The goal is to make every future AWS resource traceable by project, environment, owner, provisioning method, cost allocation, and lifecycle intent before any real AWS resources are created.

At this stage, this is a governance and FinOps standard. It does not create AWS resources and does not require `terraform apply`.

---

## 2. Why tagging matters

Tags are not only labels. In a production-oriented DevOps project, tags support:

- cost allocation,
- ownership,
- cleanup discipline,
- environment separation,
- incident response,
- auditability,
- governance,
- future automation,
- portfolio evidence that cloud maturity is cost-aware.

A resource without tags is harder to explain, harder to clean up, and harder to connect to business value.

---

## 3. Mandatory tags

Every future AWS resource that supports tags should receive the following mandatory tags through Terraform.

| Tag | Example value | Purpose |
|---|---|---|
| `Project` | `retailops` | Identifies the project or platform. |
| `Environment` | `dev` | Separates dev, staging, and future production-like scope. |
| `Owner` | `oskar` | Shows who is responsible for the resource. |
| `ManagedBy` | `terraform` | Shows that the resource is managed as Infrastructure as Code. |
| `CostCenter` | `portfolio` | Supports cost grouping and portfolio-level cost awareness. |
| `Lifecycle` | `temporary` | Shows whether the resource should be temporary or persistent. |

Current Terraform alignment in `infra/locals.tf`:

```hcl
common_tags = merge(
  {
    Project     = var.project_name
    Environment = var.environment
    Owner       = var.owner
    ManagedBy   = var.managed_by
    CostCenter  = var.cost_center
    Lifecycle   = var.resource_lifecycle
  },
  var.additional_tags
)
```

---

## 4. Optional tags

Optional tags may be added when they improve ownership, cost visibility, or evidence quality.

Recommended optional tags:

| Tag | Example value | Purpose |
|---|---|---|
| `Workload` | `platform-foundation` | Groups resources by workload or capability. |
| `Component` | `api` | Clarifies ownership at component level. |
| `Sprint` | `sprint-10` | Useful for portfolio evidence during build-out. |
| `DataClassification` | `synthetic` | Marks sample or synthetic-data scope. |
| `Criticality` | `low`, `medium`, `high` | Helps future incident and recovery prioritization. |
| `Repository` | `retailops-cloud-native-platform` | Links resource to source repository. |

Optional tags should be non-sensitive. Do not put secrets, credentials, personal data, or private client identifiers in tags.

Terraform variable:

```hcl
additional_tags = {
  Workload = "platform-foundation"
  Sprint   = "sprint-10"
}
```

---

## 5. Lifecycle policy

The `Lifecycle` tag explains whether a resource is expected to be short-lived or long-lived.

Allowed values in current Terraform:

```text
temporary
persistent
```

### temporary

Use for:

- dev experiments,
- short-lived validation environments,
- temporary proof-of-concept resources,
- resources that should be destroyed after evidence is collected.

Expected behavior:

- review cost after use,
- destroy when no longer needed,
- avoid always-on cost unless explicitly justified.

### persistent

Use for:

- shared foundation resources,
- long-lived state or registries,
- resources required across multiple validation sessions,
- future production-like platform components.

Expected behavior:

- document why the resource is persistent,
- monitor cost,
- apply stricter review before changes,
- avoid accidental deletion.

---

## 6. Environment policy

| Environment | Tag value | Cost and governance expectation |
|---|---|---|
| Development | `dev` | Lowest-cost, temporary-first, safe for experimentation. |
| Staging | `staging` | Future production-like validation, introduced after MVP stability. |
| Production-like | `prod` | Future target maturity, not part of early Sprint 10 scope. |

The current Sprint 10 Terraform scope uses `dev` only.

---

## 7. Temporary vs persistent decision examples

| Resource scenario | Recommended Lifecycle | Reason |
|---|---|---|
| Short-lived dev VPC for one validation session | `temporary` | Should be destroyed after testing. |
| ECR repository used across several release tests | `persistent` | Reusing image history may be useful. |
| One-off RDS test database | `temporary` | Avoid idle managed database cost. |
| Shared Terraform state bucket in future remote state setup | `persistent` | State storage must be stable once introduced. |
| Local-first scaffold with no AWS resources | `temporary` | No real AWS resource exists yet. |

---

## 8. Terraform usage pattern

Future resources should use `local.common_tags` by default.

Example pattern:

```hcl
tags = merge(
  local.common_tags,
  {
    Name      = "${local.name_prefix}-api-ecr"
    Component = "api"
  }
)
```

The `Name` tag should normally match the naming convention from `docs/naming-convention.md`.

The mandatory tags should come from `local.common_tags`, not be copy-pasted manually into every resource.

---

## 9. Resources that do not support tags

Some resources may not support AWS tags or may expose tagging differently.

If a resource cannot be tagged directly:

1. document the limitation,
2. tag the nearest parent resource if possible,
3. keep the Terraform name aligned with the naming convention,
4. avoid adding untagged resources silently.

---

## 10. Security rules for tags

Never put the following values into tags:

- passwords,
- tokens,
- API keys,
- secret names that reveal sensitive context,
- customer personal data,
- real client names,
- private account identifiers,
- incident-sensitive details,
- full internal URLs,
- private email addresses unless explicitly approved for ownership tagging.

Tags are often visible in billing, inventory, dashboards, logs, exports, and screenshots. Treat them as non-secret metadata.

---

## 11. FinOps review checklist

Before adding a future AWS resource, verify:

- `Project` tag exists,
- `Environment` tag exists,
- `Owner` tag exists,
- `ManagedBy` tag exists,
- `CostCenter` tag exists,
- `Lifecycle` tag exists,
- `Name` tag follows the naming convention where supported,
- temporary resources have a cleanup expectation,
- persistent resources have a reason,
- no sensitive value appears in any tag,
- `local.common_tags` is reused instead of manual copy-paste.

---

## 12. Relationship to cost evidence

These tags support future evidence for:

- estimated monthly cloud cost,
- idle baseline monthly cloud cost,
- temporary environment cleanup,
- cost per environment,
- cost per workload,
- cost risk reviews,
- portfolio screenshots from AWS Cost Explorer or reports.

In the current commit, no AWS resources are created, so the evidence is the standard itself and its alignment with Terraform variables and locals.
