# Terraform module: tags

This module centralizes the RetailOps AWS tagging and naming foundation.

It does not create AWS resources. The dev environment already uses its outputs
for module inputs and provider default tags:

- `name_prefix`,
- `required_tags`,
- `common_tags`.

The module supports the project naming convention:

```text
<project>-<environment>-<component>-<resource-type>
```

Examples (the consuming module chooses the resource suffix):

```text
retailops-dev-api
retailops-dev-network-vpc
retailops-dev-observability-log-group
```

The module also enforces the mandatory tag contract used for governance, FinOps, ownership, and cleanup decisions.
