# Full canonical sales and native return replay

The explicit `data.dq.full_run` entry point adds capture / fault-plan / fixture
version 2.0.0. It retains the selected-sales v1 CLI, limits, contracts and meaning.
The new projection includes every canonical `sales` row and every native
`return_events` row, including rejected claims and the tail after sales history.
It uses the existing OPS07 `sale_completed` and `return_completed` envelopes on
`retailops.sales.v1`, schema exactly `1.0`. No wire fields, event types or topics
are added. Native quantities become the wire's string scalars.

## Binding and boundaries

`raw_dq_binding.v2.schema.json` binds the source ID, descriptor checksum, ordered
event checksum, sales / return / total counts and the identities of exactly six
operational projection tables. Selection is all canonical facts, not sampling.
`raw_dq_capture.v2.schema.json` makes the capture version explicit; v1 rejects it.
`raw_dq_plan.v2.schema.json` contains the private fault plan. A full plan's event
count must equal the full canonical projection, and targets / anchors cannot
overlap. The source remains qualified and unchanged under raw faults.

Bounds are 4,096 canonical facts, 8,192 delivered event offsets, 16,384 total
capture records, 64 KiB per UTF-8 event body and 32 MiB per fixture artifact.
The existing source bound remains 5,000 daily product / store rows and 64 MiB
of source artifacts. Exceeding a bound fails; it never silently samples.

The full reader receives only the verified operational parent and capture.
Source seed is used solely to reproduce envelope identities. Fault plans,
injection seed, issue labels and business simulation truth are evaluator inputs
only. They never enter payloads, accepted facts or aggregate revisions.

## Native operational semantics

The wire `store_id` retains the legacy order store. The reader resolves original
selling location, stock location and currency through the verified native sale;
it does not equate legacy store IDs with native locations. Return scope is
`purchases_in_parent_source_only`. It includes the tail for those purchases,
without claiming carry-in from purchases before the source history.

`return_completed` represents a completed claim decision in this projection.
The wire has no return status or currency field: both are restored by the exact
`return_id` binding to native facts. `refunded` units contribute to refunded
units and money; `rejected` units contribute only to claim / rejected counts.
Status is never guessed from zero money. Payload, clocks, correlation and all
operational fields must match the canonical parent; a valid schema alone does
not qualify altered quantities, prices, routes or provenance. Only descriptive
`sku` (sales) and redundant `order_id` (returns) may be absent.

Deduplication separates identical event ID / content from a new envelope for the
same business fact. Conflicting event IDs are quarantined. Each accepted arrival
appends a revision at its capture delivery time; earlier as-of views stay fixed.
Aggregation grain is event type / event day / product / original selling
location / channel / currency. Money uses Decimal. Return aggregates distinguish
claim, refunded and rejected units and retain original stock location references.

## Coverage is not an event-day closure guarantee

`parent_fact_coverage` reconciles expected and accepted canonical IDs per native
grain, including missing IDs after quarantine. It describes coverage of this
finite parent only. Even a clean capture covering all parent facts retains
`business_event_day_completeness=not_qualified`. Missing grains stay unknown and
have no invented zero. Aggregate revisions remain partial operational evidence.

Progress records declare a frontier for `all_parent_sales_and_return_claims` at
an exact capture position. They support late-arrival tests; maximum event time
is not a watermark. Neither explicit fixture progress nor purchase-cohort
maturity proves business event-day closure. A separate reviewed event-day
coverage policy and independent AI consumer are still required before model
qualification or dense zero-valued anomaly observations.

## Faults, publication and reproduction

The example applies all eight reviewed faults to each wire type: exact and
business duplicate, late and out-of-order arrival, missing optional context,
unsupported major / minor and an unexpected additive field. Private evaluation
joins truth afterward, reconciles all 16 expected actions, exact business facts,
totals, six quarantined / missing parent facts and replay idempotence.

The immutable fixture has the same six artifact paths plus manifest as v1.
Generation stages and fully verifies content before publication. Reuse verifies
existing bytes; verification rebuilds the complete projection / faults / replay
from the external verified source. Self-resealed false totals are rejected.
The public handoff remains only `raw/events.jsonl` and `source_binding.json`;
private plans and evaluation must not be copied into runtime inputs.

```bash
python -m data.dq.full_run --source-dir "$SOURCE_DIR" --example \
  --output-root /tmp/ai07-full-dq --output /tmp/ai07-full-dq.json
python -m data.dq.full_run --source-dir "$SOURCE_DIR" --verify "$FIXTURE_DIR" \
  --output /tmp/ai07-full-dq-verified.json
python -m data.dq.full_check --workspace /tmp/ai07-full-dq-fresh \
  --output /tmp/ai07-full-dq-acceptance.json
```

The final command requires a fresh workspace and runs both 30-day anomaly cases
twice in separate processes. It compares source / fixture IDs, every source
artifact checksum and all publication checksums, and enforces 300 seconds /
1024 MiB per complete process. The source manifest is compared semantically,
excluding only its wall-clock `generated_at`; both actual timestamps and full
manifest checksums are retained. Every source byte stays fixed within each run.
Required Data CI runs this acceptance on Python 3.11.15 and tests negative cases.
This is producer-side offline evidence, not broker durability, ACK, live DLQ,
an AI03 snapshot publication, an independent AI replay or model readiness.
