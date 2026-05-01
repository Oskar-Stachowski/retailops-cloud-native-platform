# RetailOps demo data

This directory contains a deterministic demo dataset generator for the
RetailOps API database.

## Structure

```text
data/
  demo/                 # generated CSV files used by the API seed script
  generator/            # Python rules that generate realistic demo data
```

The generator creates products, users, sales, inventory snapshots, forecasts,
anomalies, alerts, recommendations and workflow actions. The goal is to keep
business rules in Python and keep SQL seeding limited to loading validated CSV
files into PostgreSQL.

## Generate CSV files

From the repository root:

```bash
python -m data.generator.main
```

This writes CSV files to:

```text
data/demo/
```

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
