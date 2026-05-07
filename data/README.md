# RetailOps demo data

This directory contains a deterministic demo dataset generator for the
RetailOps API database.

## Structure

```text
data/
  demo/                 # generated CSV files used by the API seed script
  generator/            # Python rules that generate realistic demo data
```

The generator creates products, users, stores, warehouses, orders, order items,
price history, promotions, stock movements, returns, sales, inventory snapshots,
forecasts, anomalies, alerts, recommendations and workflow actions. The goal is
to keep business rules in Python and keep SQL seeding limited to loading
validated CSV files into PostgreSQL.

The current dataset is intentionally small and optimized for local API tests.
The target strategy for larger generated datasets is documented in
[RetailOps Synthetic Data Profiles](../docs/synthetic-data-profiles.md).

## Generate CSV files

From the repository root:

```bash
python -m data.generator.main
```

This writes CSV files to:

```text
data/demo/
```

The generator also accepts the target synthetic data options that will be used
by later scalable profiles:

```bash
python -m data.generator.main \
  --profile demo \
  --days 14 \
  --products 20 \
  --stores 4 \
  --warehouses 4 \
  --seed 42
```

The `demo` profile writes to `data/demo` by default. The `small`, `medium`, and
`large` profiles write to `data/synthetic/<profile>` by default and are ignored
by Git. Their sizing strategy is documented in
[RetailOps Synthetic Data Profiles](../docs/synthetic-data-profiles.md).

Synthetic profiles beyond `demo` include a realism layer:

- deterministic randomness controlled by `--seed`,
- product demand classes and long-tail demand distribution,
- weekly and seasonal demand patterns,
- price elasticity and promotion uplift,
- stockout-limited observed sales with separate latent demand,
- multi-item baskets,
- category and channel-specific returns,
- inventory replenishment-style stock movements,
- anomalies derived from generated business signals,
- low-rate controlled data quality statuses.

For non-demo profiles, the generator also writes:

```text
realism_report.json
```

The report summarizes row counts and realism checks such as top-product revenue
share, average order items, promotion uplift, stockout rate, return rate by
category and data quality status counts.

## Seed the API database

From `services/api`:

```bash
python scripts/seed_demo_data.py
```

The seed script expects `DATABASE_URL` to point to the PostgreSQL database. It
is idempotent: before inserting the generated CSV data, it truncates the demo
application tables and reloads them in dependency order.

## Run seed tests

From `services/api`:

```bash
pytest tests/test_seed_data.py
```

The test suite regenerates the CSV files before seeding the database, then
checks row counts, relationships, basic data quality and idempotency.
