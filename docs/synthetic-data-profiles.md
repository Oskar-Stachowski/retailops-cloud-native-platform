# RetailOps Synthetic Data Profiles

## 1. Purpose

This document defines the target synthetic data profiles for the RetailOps
Cloud-Native Platform.

The current `data/demo` dataset is intentionally small. It is useful for API
contracts, seed tests, and local dashboard smoke checks, but it is not large or
rich enough for advanced AWS data flows, real-time analysis, observability, or
MLOps.

The goal of the synthetic data strategy is to keep a fast deterministic demo
dataset while adding larger generated datasets that can exercise the platform
like a realistic retail operations system.

## 2. Current Baseline

The current generator creates deterministic CSV files for:

- products
- users
- sales
- inventory snapshots
- forecasts
- anomalies
- alerts
- recommendations
- workflow actions

The dataset currently represents a compact MVP flow:

```text
Product + Sale + InventorySnapshot
        -> Forecast / Anomaly
        -> Alert
        -> Recommendation
        -> WorkflowAction
        -> User decision
```

This remains the correct shape for `demo`, but future profiles must introduce
time series depth, location variety, higher record volume, controlled data
quality issues, and event streams.

## 3. Profile Summary

| Profile | Purpose | Stored in repo | Primary format | Expected runtime |
| --- | --- | --- | --- | --- |
| `demo` | Fast API seed, contract tests, local presentation | Yes | CSV | Seconds |
| `small` | Local development with realistic enough data | No, generated locally | CSV or Parquet | Minutes |
| `medium` | Docker/Kubernetes/AWS dev, first MLOps and real-time replay | No | Parquet + JSONL + serving DB subset | Minutes to tens of minutes |
| `large` | Data lake, performance, cost-controlled advanced platform evidence | No | Parquet on S3 or local object storage | Long-running batch |

## 4. Profile Targets

### 4.1 `demo`

`demo` is the stable seed used by the API service and tests.

Target size:

| Data area | Target |
| --- | ---: |
| Products | 8-20 |
| Users | 4-10 |
| Locations | 1-4 represented as region or warehouse fields |
| History | 7-14 days |
| Sales rows | Up to 1,000 |
| Inventory snapshots | Up to 1,000 |
| Alerts/anomalies/recommendations | 4-50 |

Expected use:

- API seed data
- local full-stack Docker Compose demo
- contract tests
- deterministic dashboard screenshots
- smoke tests

Storage guidance:

- CSV files can stay in `data/demo`.
- Data should remain deterministic and small enough to review manually.
- The generator should continue to support stable IDs for test assertions.

### 4.2 `small`

`small` is the first profile that should feel operational instead of purely
demonstrative.

Target size:

| Data area | Target |
| --- | ---: |
| Products | Around 100 |
| Stores/locations | Around 5 |
| Warehouses | Around 3 |
| History | Around 90 days |
| Sales/order item rows | 20,000-50,000 |
| Inventory snapshots | 9,000-50,000 |
| Stock movements | 20,000-100,000 |
| Alerts/anomalies/workflow actions | 1,000-5,000 |

Expected use:

- local development
- heavier API and repository tests
- dashboard pagination and filtering
- basic data quality checks
- first simple forecasting experiments

Storage guidance:

- Generated locally, not committed.
- CSV is acceptable, but Parquet should be supported if dependencies are added.
- PostgreSQL can hold this profile for local development.

### 4.3 `medium`

`medium` is the main platform engineering profile. It should be large enough to
justify data pipelines, observability, batch processing, and real-time replay.

Target size:

| Data area | Target |
| --- | ---: |
| Products | 1,000-5,000 |
| Stores/locations | 20-50 |
| Warehouses | 5-10 |
| History | 365-730 days |
| Sales/order item rows | 1,000,000-10,000,000 |
| Inventory snapshots | 500,000-5,000,000 |
| Stock movements | 1,000,000-20,000,000 |
| Event stream records | 1,000,000-20,000,000 |
| Alerts/anomalies/workflow actions | 50,000-500,000 |

Expected use:

- AWS data lake development
- Kubernetes runtime checks
- real-time event replay
- MLOps feature generation
- model evaluation
- observability dashboards
- load and performance smoke tests

Storage guidance:

- Historical data should be written as Parquet.
- Real-time replay data should be written as JSONL or published directly to a
  broker.
- Only serving aggregates or sampled operational records should be loaded into
  PostgreSQL.
- Full datasets should not be committed to Git.

### 4.4 `large`

`large` is an optional advanced evidence profile for a mature platform demo. It
should be used carefully because it can create meaningful compute and storage
costs in AWS.

Target size:

| Data area | Target |
| --- | ---: |
| Products | 10,000-100,000 |
| Stores/locations | 100+ |
| Warehouses | 20+ |
| History | 2-3 years |
| Sales/order item rows | 50,000,000+ |
| Inventory snapshots | 10,000,000+ |
| Event stream records | 50,000,000+ |

Expected use:

- S3/Glue/Athena evidence
- large batch processing tests
- performance and partitioning validation
- cost monitoring
- data lifecycle policy validation

Storage guidance:

- S3 or local object storage only.
- Parquet is required.
- Partition by event date or business date.
- Apply lifecycle policies before generating this profile in AWS.
- Keep generation and cleanup runbooks close to the Terraform environment.

## 5. Target Data Domains

Future generated datasets should expand beyond the current MVP tables.

Recommended next domains:

| Domain | Why it matters |
| --- | --- |
| `stores` | Enables location-level demand, regional dashboards, and store operations. |
| `warehouses` | Enables stock positioning, replenishment, and supply chain signals. |
| `suppliers` | Enables procurement and replenishment scenarios. |
| `orders` | Separates business orders from individual sales rows. |
| `order_items` | Enables basket, item-level, and revenue analysis. |
| `stock_movements` | Enables real inventory flow rather than point-in-time snapshots only. |
| `price_history` | Enables pricing analysis and realistic demand forecasting. |
| `promotions` | Enables seasonality, uplift, cannibalization, and forecast features. |
| `returns` | Enables net sales and quality scenarios. |
| `ingestion_batches` | Enables data freshness, lineage, and pipeline observability. |
| `data_quality_checks` | Enables governance and operational data quality reporting. |
| `model_versions` | Enables MLOps traceability. |
| `forecast_runs` | Connects forecasts to model versions, inputs, and evaluation metrics. |
| `audit_logs` | Enables operational governance and security evidence. |

## 6. File Formats and Storage Layers

### CSV

Use CSV for:

- small deterministic demo seed
- simple local test fixtures
- human-readable contract examples

Avoid CSV for:

- large history
- data lake storage
- MLOps feature datasets
- high-volume event replay

### Parquet

Use Parquet for:

- historical sales
- inventory history
- stock movements
- feature datasets
- forecast outputs
- Athena and Glue-backed analysis

Recommended partitioning:

```text
data/synthetic/medium/sales/year=2026/month=05/day=07/*.parquet
data/synthetic/medium/inventory/year=2026/month=05/day=07/*.parquet
data/synthetic/medium/features/demand_forecast/year=2026/month=05/*.parquet
```

AWS target:

```text
s3://retailops-data-lake/raw/sales/year=2026/month=05/day=07/*.parquet
s3://retailops-data-lake/processed/inventory/year=2026/month=05/day=07/*.parquet
s3://retailops-data-lake/curated/features/demand_forecast/year=2026/month=05/*.parquet
```

### JSONL

Use JSONL for:

- replayable event streams
- dead-letter event examples
- operational telemetry samples

Example:

```json
{"event_id":"uuid","event_type":"sale_completed","schema_version":"1.0","occurred_at":"2026-05-07T10:15:30Z","payload":{"product_id":"uuid","store_id":"WAW-001","quantity":2}}
```

## 7. Real-Time Analysis Requirements

The synthetic data platform must support both historical batch generation and
real-time event generation.

Required event types:

- `sale_completed`
- `order_created`
- `stock_changed`
- `inventory_snapshot_recorded`
- `price_changed`
- `promotion_started`
- `forecast_generated`
- `anomaly_detected`
- `alert_created`
- `workflow_action_performed`

Required event fields:

- `event_id`
- `event_type`
- `schema_version`
- `source`
- `correlation_id`
- `occurred_at`
- `ingested_at`
- `payload`

Real-time analysis should support:

- sales units and revenue for the last 5, 15, and 60 minutes
- stockout risk by product and location
- event lag and freshness
- failed event counts
- dead-letter records
- live alert creation

## 8. MLOps Data Requirements

A meaningful forecasting pipeline needs at least:

- 1-2 years of sales history
- daily grain by `date`, `product_id`, `store_id`, and `channel`
- product metadata
- price history
- promotion flags
- stockout flags
- calendar features
- inventory availability
- controlled anomalies

Recommended feature grain:

```text
date + product_id + store_id + channel
```

Recommended target:

```text
units_sold
```

Recommended metrics:

- MAE
- RMSE
- MAPE
- bias
- data drift score
- forecast freshness

## 9. Dataset Manifest

Every generated dataset profile should produce a manifest.

Recommended manifest fields:

```json
{
  "dataset_name": "retailops-synthetic",
  "profile": "medium",
  "schema_version": "1.0",
  "generator_version": "0.1.0",
  "seed": 42,
  "generated_at": "2026-05-07T12:00:00Z",
  "date_start": "2025-05-01",
  "date_end": "2026-04-30",
  "formats": ["parquet", "jsonl"],
  "row_counts": {
    "products": 1000,
    "stores": 25,
    "sales": 2500000
  }
}
```

## 10. Quality Gates

Each non-demo profile should have data quality checks.

Minimum checks:

- no negative quantities
- no negative prices
- required foreign keys exist
- timestamps are valid and ordered
- required partitions exist
- row counts match the manifest
- controlled anomaly rate stays within expected bounds
- duplicate event rate stays below threshold
- event lag can be computed from timestamps

These checks should produce a report that can be stored in `ci-cd/reports/data/`.

## 11. Git Policy

Recommended repository policy:

- commit `data/demo`
- commit schemas, generator code, tests, and small examples
- do not commit `small`, `medium`, or `large` generated datasets
- do not commit generated Parquet files
- do not commit generated event replay files beyond tiny examples
- keep generated heavy data in local ignored folders, object storage, or S3

Recommended ignored generated paths:

```text
data/synthetic/
data/generated/
data/replay/
```

