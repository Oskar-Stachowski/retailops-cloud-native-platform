# Live Metrics Persistence

This sprint stores real-time processing output in PostgreSQL so the API can
serve live operational views without rebuilding state from raw events on every
request.

## Tables

`realtime_event_log`

- One row per source event.
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
For accepted events it writes the event log first, then metric observations,
then the final processed state.

That keeps replay safe and lets the real-time stream be regenerated from the
synthetic replay files without double counting live metrics.

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
