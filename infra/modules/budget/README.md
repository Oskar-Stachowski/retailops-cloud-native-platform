# Budget Module

This module defines the RetailOps AWS Budget / FinOps baseline for the dev AWS foundation.

## Purpose

The module creates an AWS monthly cost guardrail before the environment becomes a real, long-running AWS runtime.

It is intentionally small:

- one monthly `aws_budgets_budget`,
- a low default dev limit,
- optional email notifications,
- no private notification addresses in committed examples,
- tagging aligned with the shared `tags` module.

## Current scope

| Capability | Status |
|---|---|
| Monthly cost budget | Enabled by default |
| Default limit | 10 USD |
| Budget notifications | Disabled by default |
| Private email addresses in repo | Not required |
| Terraform apply | Separate decision, not part of this commit |

## Notification policy

Real notification email addresses should not be committed to the repository.

Use committed examples for safe defaults:

```hcl
enable_budget_notifications         = false
budget_notification_email_addresses = []
```

Use a local, non-committed `terraform.tfvars` file when real alerts are needed:

```hcl
enable_budget_notifications         = true
budget_notification_email_addresses = ["your-private-email@example.com"]
```

Do not put private emails, account IDs, billing contact names, or client identifiers in committed Terraform files.

## Why this matters

Budgeting is an architecture control, not only a finance task. This module shows that RetailOps treats cloud cost as part of platform quality, together with security, delivery, reliability, and observability.
