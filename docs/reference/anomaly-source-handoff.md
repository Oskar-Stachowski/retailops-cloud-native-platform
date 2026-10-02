# Anomaly source 2.8 and snapshot 1.2

Source 2.8 retains the 58 source tables and their established schemas/grains. An
explicit private plan changes the demand or physical simulation before facts are
generated. The two independent fixtures cover demand spikes/drop and physical
returns/stock censoring respectively. They are not a composite five-injection
source. Raw DQ packages bind separately to each source ID and never alter those
canonical facts.

The source reader checks current code/dependency/Python provenance, regenerates
all tables, compares the complete private effects document and recomputes the
existing 36 source gates. Two additional hard gates record process replay and
effect reconciliation. A checksum-resealed truth-only change still fails replay.
Source 2.7 and snapshot 1.1 retain their default generation/transport paths.

Snapshot 1.2 carries source 2.8 through the inventory exporter. Public exports
contain the 43 operational fact tables. Private exports require explicit truth
opt-in and additionally carry the 12 truth tables, qualified inventory windows,
`evaluation_truth/anomaly_scenario.json` and
`evaluation_truth/inventory_configuration.json`. The private variant has a
different snapshot ID and must use separate immutable storage. Neither plan nor
effects is written into normal facts. Packaged schemas describe allowed fields;
they contain no scenario instance.

Producer verification checks byte and typed logical hashes, Arrow metadata,
source/qualification identity, metadata/table allowlists and ledger conservation.
Private producer verification also regenerates the full process and qualified
labels. The independent AI verifier uses packaged contracts and source identities
without importing the generator. Import acceptance does not qualify curated
anomaly features or a model.

## Reproduce

Use the project Python with its pinned API requirements, from the producer root:

```sh
python -m data.anomalies.run_source --example --products 8 \
  --output-root data/generated/ai07/demand/sources \
  --output data/generated/ai07/demand/source-receipt.json
python -m data.anomalies.run_source --physical-example --products 8 \
  --output-root data/generated/ai07/physical/sources \
  --output data/generated/ai07/physical/source-receipt.json
```

Read `directory` and `dataset_id` from the appropriate receipt. Qualify that exact
parent with `python -m data.inventory.run_qualification`, using `--source`,
`--output-root` and a separate `--output` receipt. Then export with:

```sh
python -m data.export.inventory_snapshot --source-dir "$SOURCE_DIR" \
  --dataset-id "$SOURCE_ID" --qualification-dir "$QUALIFICATION_DIR" \
  --output-root data/generated/ai07/snapshots
```

For private evaluation add `--include-evaluation-truth` and a different output
root. Generate the eight raw faults with `python -m data.dq.run --source-dir
"$SOURCE_DIR" --example --event-limit 256 --output-root data/generated/ai07/dq
--output data/generated/ai07/dq-receipt.json`. Verification receipts must remain
outside the immutable source/package directories.

## Remaining AI07 work

The handoff is the input boundary for anomaly curation/features, PIT-safe
historical expected values and residual/scale, seasonal-residual baseline,
Isolation Forest, observation/episode evaluation and AI05 lifecycle integration.
Existing forecast artifacts are not automatically qualified for these parents.
The DQ evidence remains a bounded selected-sales offline replay; it does not
declare full curated completeness or broker/ACK/DLQ durability (AI10).
