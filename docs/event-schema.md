# RetailOps event schema

RetailOps uses a simple versioned event-envelope contract for local event-ready design. The detailed long-form design remains in `docs/real-time-event-contracts.md`; this file is the shorter checklist-facing evidence path for DB-011.

## Contract source

- Event contract: `events/contracts/retailops-realtime-events.v1.contract.json`
- Database persistence tables: `realtime_event_log`, `live_metric_observations`, `realtime_consumer_state`
- Long-form design: `docs/real-time-event-contracts.md`

## Envelope fields

| Field | Purpose |
| --- | --- |
| `event_id` | Idempotency key and event-log primary key. |
| `event_type` | Business event name, for example `sale_completed` or `alert_created`. |
| `topic` | Logical stream name, for example `retailops.inventory.v1`. |
| `schema_version` | Versioned payload/envelope compatibility marker. |
| `source` | Producing service or synthetic generator. |
| `correlation_id` | Traceability across related events. |
| `occurred_at` | Business occurrence timestamp. |
| `ingested_at` | Platform ingestion timestamp. |
| `payload` | Event-specific JSON payload. |

## Validation command

```bash
make data-contracts
```

The command validates the event contract shape together with the synthetic dataset contract and writes `ci-cd/reports/data/data-contract-report.json`.

## Claim boundary

Safe claim after validation:

> RetailOps has event-ready contracts, event-log tables, and synthetic event schemas that can be used by a future broker/CDC flow.

Careful claim:

> This is not a production CDC implementation by itself. A real broker, producer/consumer deployment, replay policy and operational runbook are still required before claiming production CDC.
