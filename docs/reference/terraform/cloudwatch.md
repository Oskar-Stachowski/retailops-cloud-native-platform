# CloudWatch Logging Module

This module defines a minimal AWS-native logging baseline for the RetailOps dev environment.

## Current scope

The module creates the log groups supplied in `log_groups`. The dev example configures:

- API logs,
- frontend logs,
- platform/foundation logs.

Default log group names follow this pattern:

```text
/<project>/<environment>/<component>
```

Example:

```text
/retailops/dev/api
/retailops/dev/frontend
/retailops/dev/platform
```

## Cost-control decision

The dev example sets retention to **7 days**. Each log-group input can specify
`retention_in_days`, optional `kms_key_id` and `skip_destroy`. Retention and
cleanup behavior should match the deployed workload's data requirements.

## Out of scope

This module does not configure:

- CloudWatch alarms,
- metric filters,
- dashboards,
- log subscriptions,
- OpenSearch forwarding,
- full enterprise observability.

Creating a log group does not configure an application log shipper or establish
that logs are ingested. Cloud activation must provide and validate that path.
