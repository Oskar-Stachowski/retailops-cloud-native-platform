# Terraform module: tags

This module centralizes the RetailOps AWS tagging and naming foundation.

It does not create any AWS resources. It only produces reusable values that future modules can consume:

- `name_prefix`,
- `required_tags`,
- `common_tags`.

The module supports the project naming convention:

```text
<project>-<environment>-<component>-<resource-type>
```

Example future names:

```text
retailops-dev-api-ecr
retailops-dev-network-vpc
retailops-dev-observability-log-group
```

The module also enforces the mandatory tag contract used for governance, FinOps, ownership, and cleanup decisions.
