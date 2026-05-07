# CloudWatch Logging Module

This module defines a minimal AWS-native logging baseline for the RetailOps dev environment.

## Current scope

The module creates short-retention CloudWatch Log Groups for:

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

The default retention is **7 days**. This is intentional for Sprint 10 because the goal is to prove AWS-native logging lifecycle management without introducing unnecessary long-term storage cost.

## Out of scope

This module does not configure:

- CloudWatch alarms,
- metric filters,
- dashboards,
- log subscriptions,
- OpenSearch forwarding,
- full enterprise observability.

Those controls should be added later only when the runtime architecture and alerting model are clear.
