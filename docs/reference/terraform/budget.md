# Budget Module

This module defines the RetailOps AWS Budget / FinOps baseline for the dev AWS foundation.

## Purpose

The module creates an AWS monthly cost guardrail when enabled by its calling environment. It does not enforce a spending cap
or automatically stop resources. The current resource has no Project-tag cost
filter; account-wide costs can contribute to this budget.

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
| Limit | Set through `monthly_budget_limit_usd`; the example value is not a cost estimate |
| Budget notifications | Disabled by default |
| Private email addresses in repo | Not required |
| Deployment | Part of the [AWS activation plan](../../plans/aws-activation.md) |

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

The examples above are inputs to `infra/environments/dev`. The module itself
uses `enable_budget_notifications` and `notification_email_addresses`.
Review the budget and recipients against the intended account and experiment.
