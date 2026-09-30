# Live Metrics Persistence

The consumer stores real-time processing output in PostgreSQL so the API can
serve live operational views without rebuilding state from raw events on every
request.

## Tables

`realtime_event_log`

- One row per source event, plus durable transport quarantine records.
- Stores envelope metadata, topic, processing status, attempt count, payload and
  timestamps.
- Status values used by the consumer:
  - `received`
  - `processed`
  - `failed_dead_lettered`
  - `ignored_duplicate`

`live_metric_observations`

- One or more rows derived from a processed event.
- Stores normalized metric name, numeric value, dimension key and observed time.
- Rows are replaced on reprocessing so the event stays idempotent.

`realtime_consumer_state`

- One row per consumer name.
- Stores counters for received, processed, failed, dead-lettered and ignored
  events.
- Also stores the last processed event metadata and lifecycle timestamps.

## Metric Derivation

The consumer derives simple live measures from the event envelope payload:

- sales events produce revenue and unit counters,
- returns produce refund and return-unit counters,
- inventory events produce stock and replenishment counters,
- pricing events produce price-change counters,
- intelligence and operations events produce their own operational counters.

The aim is not a full analytical warehouse. The goal is a stable operational
read model that can back real-time dashboard cards, alert badges and stream
health checks.

## Idempotency

The consumer treats already processed events as duplicates and ignores them.
For accepted events the event log, metric observations and final processed
marker share one PostgreSQL transaction. A transaction advisory lock on the
event UUID serializes concurrent deliveries before the duplicate check.
An interrupted transaction leaves neither partial metrics nor a processed marker.
State counters are stored afterwards; a failure there leaves the offset pending
and the next delivery uses the already committed marker.

That keeps replay safe and lets the real-time stream be regenerated from the
synthetic replay files without double counting live metrics.

Rejected JSON/envelopes use a separate synthetic UUID derived from consumer
group/topic/partition/offset. Their source is `retailops.consumer.quarantine`,
type `transport_rejected`, status `failed_dead_lettered`. Their payload retains
base64-encoded value/key/headers, the broker timestamp and transport coordinates.
The runner confirms that immutable content from the committed database row
before acknowledging. No message is published to `retailops.dlq.v1` in this path.
Handler/database failures escape and stop polling without acknowledging;
they are not reported as successful dead-letter deliveries.

[Recovery and reviewed replay](../runbooks/realtime-recovery.md) preserve the
original bytes and pin a correction before publication. External effects from
custom handlers require their own idempotency/transaction design; current
default handlers have no external effects. Business-key revisions and AI
domain projections remain part of stage 10.

## API Read Model

`GET /dashboard/live-operations` returns the live dashboard read model backed by
these tables.

The response includes:

- live sales, returns, stock, anomaly and alert counters for a trailing window,
- event status counters,
- latest event freshness,
- recent stream events,
- recent alert-like events,
- persisted consumer state.
