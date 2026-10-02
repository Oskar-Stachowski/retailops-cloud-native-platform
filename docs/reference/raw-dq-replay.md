# Raw DQ fixtures and bounded offline sales replay

AI07.2 generates eight deterministic faults in captured raw events, with a bounded
AI07.3 reader that demonstrates their handling. Canonical source 2.7 CSVs, commerce
facts and inventory ledger remain unchanged. Business anomaly injection is a
separate workstream (PR #78); this fixture does not require that branch.

## Contracts and scope

- `data/contracts/raw_dq_plan.v1.schema.json`: private plan bound to the source ID,
  selected event checksum, seed and generator version. Targets and timing anchors
  cannot overlap. The list order has no effect on the result.
- `data/contracts/raw_dq_capture.v1.schema.json`: raw event bytes plus delivery time,
  topic, partition, offset and content-derived record ID. Separate control records
  declare completeness through an event-time frontier for the selected fixture.
- The reader uses the unchanged OPS07 executable legacy v1 schema. It accepts only
  the operational `sale_completed` projection from the synthetic producer and
  versions supported by that contract, currently exactly `1.0`.
- Selection is chronological, equally spaced, includes both endpoints, and is
  limited to 12–512 sales (default 256). A parent has at most 5,000 daily product /
  store rows and 64 MiB of table artifacts. This is a bounded test fixture.

The projection explicitly allows operational fields and excludes latent demand,
stockout flags and injection labels. `ingested_at` is the later of the canonical
sale ingestion and its inventory sale availability. `received_at` is the delivery
time in the offline capture; faults never move it before source availability.

| Fault | Raw effect | Reader action |
|---|---|---|
| Exact duplicate | Extra byte-identical envelope, new offset | Deduplicate by event ID and content |
| Business duplicate | Extra envelope with a new event ID | Deduplicate by producer + sale ID and business version |
| Late event | Move a fact behind a declared earlier-day frontier | Accept as late; append an aggregate revision |
| Out of order | Deliver an earlier fact after a later fact on the same day | Accept as out of order; append a revision |
| Missing optional context | Remove `sku` | Accept with unchanged business semantics |
| Unsupported major | Set schema version to `2.0` | Quarantine, offline DLQ reference |
| Unsupported minor | Set schema version to `1.1` | Quarantine, offline DLQ reference |
| Unexpected additive field | Add unknown payload context | Quarantine under the closed legacy schema |

Conflicting content under an existing event ID is quarantined. A different business
fact under an existing sale ID also requires quarantine: legacy v1 has no explicit
business revision sequence, so the reader cannot infer a replacement safely.
New late facts can revise totals; they do not replace prior facts.

## Time and reconciliation

Daily aggregates use the legacy `business_date / product_id / store_id / channel /
currency` grain. Money is summed with Decimal. Missing grains have no row, never
an invented zero. Each accepted fact appends an immutable aggregate version with
`known_at`, a raw reference and a predecessor revision ID. Queries at an earlier
cutoff keep their earlier result after a late arrival.

`declared_source_watermark` comes only from explicit progress records.
`max_accepted_event_time` is reported separately and never establishes completeness.
The progress declarations concern only selected fixture sales. Sampling and
quarantine leave `curated_completeness=not_qualified` even at the final frontier.
These control records are local fixture metadata, not new broker events or topics.

Private `simulation_truth/data_quality_injections.json` contains event/raw references,
issue, expected action, seed and all three timestamps. The reader receives raw
records only. The evaluator joins private truth afterward, compares every expected
and observed action, checks business versions and aggregate totals against the
source projection, and replays the identical capture twice to prove idempotence.
An identical record ID is a no-op; reusing its offset with different bytes fails.

## Immutable package and reproduction

`data.dq.run` publishes a content-addressed package containing raw JSONL, operational
replay output, source binding, private plan, truth and evaluation, plus a manifest.
Identity covers content, source, plan, versions, implementation and dependencies.
Writing is staged and verified before publication. Existing content is verified,
never overwritten. Verification requires the external source parent and rebuilds
the projection, faults and replay; self-resealed artifact tampering is rejected.
The verifier requires the matching implementation, Python and locked dependencies.

Example (use the dataset directory from the source receipt as `SOURCE_DIR`):

```bash
python -m data.inventory.run_source_dataset \
  --profile ai-smoke --days 14 --products 8 --stores 3 --warehouses 2 --seed 42 \
  --output-root /tmp/ai07-source --output /tmp/ai07-source-receipt.json

python -m data.dq.run --source-dir "$SOURCE_DIR" --example --seed 42 \
  --event-limit 256 --output-root /tmp/ai07-dq-a --output /tmp/ai07-dq-a.json
python -m data.dq.run --source-dir "$SOURCE_DIR" --example --seed 42 \
  --event-limit 256 --output-root /tmp/ai07-dq-b --output /tmp/ai07-dq-b.json

python -m data.dq.run --source-dir "$SOURCE_DIR" --verify "$FIXTURE_DIR" \
  --output /tmp/ai07-dq-verified.json
```

`--plan` accepts a frozen private plan instead of `--example`. An example requires
multiple days and distinct event times within a day for meaningful timing tests.
Outputs must be outside the canonical source; verification receipts must also be
outside the immutable fixture.

## Remaining AI07 work

This package is offline only. It proves no durable broker delivery, ACK, live DLQ,
database recovery or production projection behavior (AI10). It is not an AI03
snapshot publication and marks handoff/model readiness false. It does not qualify
anomaly labels or train/evaluate a detector. AI07 still requires the combined
scenario handoff, PIT-safe features, seasonal residual baseline, Isolation Forest,
evaluation and AI05 lifecycle/serving integration.
