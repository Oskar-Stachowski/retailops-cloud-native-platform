# RetailOps Database Schema, Migrations and Demo Seed Data

## Purpose

This document describes the first database migration and demo seed data for the RetailOps Cloud-Native Platform.

The goal of this task is to provide a repeatable PostgreSQL database setup for local development, tests, and future API/service layer work.

## Scope

This task covers:

- initial PostgreSQL schema creation with Alembic,
- core RetailOps tables,
- base indexes and constraints,
- realistic demo data for retail operations,
- seed data validation,
- basic database schema tests.

## Current Database Tables

The database currently contains the following application tables:

| Table | Purpose |
|---|---|
| `products` | Product master data, including SKU, name, category, brand, and status. |
| `users` | Demo users representing operational roles such as inventory planner, category manager, analyst, and admin. |
| `sales` | Historical sales transactions connected to products. |
| `inventory_snapshots` | Stock snapshots by product and warehouse. |
| `forecasts` | Demand forecast records for selected products. |
| `anomalies` | Detected business anomalies such as sales drops, stale inventory, pricing issues, or demand spikes. |
| `alerts` | Operational alerts created from anomalies and assigned to users. |
| `recommendations` | Business recommendations generated from forecasts, anomalies, or alerts. |
| `workflow_actions` | User actions performed on alerts, such as acknowledge, assign, resolve, or comment. |

The database also contains the Alembic metadata table:

| Table | Purpose |
|---|---|
| `alembic_version` | Tracks the currently applied Alembic migration revision. |

## Migration

The initial migration creates the RetailOps database schema.

Example migration status:

```bash
python -m alembic current
```

Expected result:

```text
9d505dd3b320 (head)
```

To apply all migrations:

```bash
python -m alembic upgrade head
```

To inspect available tables in PostgreSQL:

```bash
docker exec -it retailops-cloud-native-platform-db-1 psql -U retailops -d retailops -c "\\dt"
```

Expected tables:

```text
alembic_version
alerts
anomalies
forecasts
inventory_snapshots
products
recommendations
sales
users
workflow_actions
```

## Main Schema Design

### Products

The `products` table is the central product master table.

Important design choices:

- `sku` is unique and required.
- `status` is limited to allowed product lifecycle states.
- indexes are added for common lookup fields such as `sku` and `category`.

Example fields:

- `id`
- `sku`
- `name`
- `category`
- `brand`
- `status`
- `created_at`
- `updated_at`

### Sales

The `sales` table stores transactional product sales.

Important design choices:

- each sale references a product through `product_id`,
- quantity must be positive,
- monetary values must be non-negative,
- currency is constrained to supported values,
- sales can be filtered by `sold_at`.

### Inventory Snapshots

The `inventory_snapshots` table stores stock levels at specific points in time.

Important design choices:

- each snapshot references a product,
- stock quantity cannot be negative,
- `warehouse_code` cannot be empty,
- `recorded_at` must not be later than `ingested_at`.

### Forecasts

The `forecasts` table stores demand forecasts.

Important design choices:

- each forecast references a product,
- predicted quantity cannot be negative,
- forecast period start must be before or equal to forecast period end,
- confidence level must be between `0` and `1`,
- forecast status and method are constrained to allowed values.

### Anomalies

The `anomalies` table stores detected business issues.

Important design choices:

- each anomaly references a product,
- anomaly type is constrained to predefined business categories,
- severity is constrained to allowed severity levels,
- period start must be before or equal to period end.

### Alerts

The `alerts` table represents operational alerts created from anomalies.

Important design choices:

- each alert references a product,
- an alert may reference an anomaly,
- an alert may be assigned to a user,
- status and severity are constrained to allowed values,
- title and recommended action must have minimum meaningful length.

### Recommendations

The `recommendations` table stores suggested actions for business users.

Important design choices:

- each recommendation references a product,
- it may optionally reference a forecast, anomaly, or alert,
- recommendation status and type are constrained,
- `expires_at` must not be earlier than `generated_at`.

### Workflow Actions

The `workflow_actions` table stores the operational history of alert handling.

Important design choices:

- each workflow action references an alert,
- each workflow action is performed by a user,
- action type is constrained,
- previous and new status values are constrained,
- optional comments must have meaningful length when provided.

## Foreign Key Strategy

The schema uses foreign keys to preserve relationships between business objects.

Examples:

- `sales.product_id` references `products.id`
- `inventory_snapshots.product_id` references `products.id`
- `forecasts.product_id` references `products.id`
- `anomalies.product_id` references `products.id`
- `alerts.product_id` references `products.id`
- `alerts.assigned_to_user_id` references `users.id`
- `recommendations.product_id` references `products.id`
- `workflow_actions.alert_id` references `alerts.id`
- `workflow_actions.performed_by_user_id` references `users.id`

For product-dependent records, `ON DELETE CASCADE` is used where removing a product should also remove dependent operational data.

For optional analytical references, `ON DELETE SET NULL` is used where the recommendation or alert may still be useful even if the linked source record is removed.

## Demo Seed Data

The seed script inserts realistic demo data for local development.

Seed script location:

```text
services/api/scripts/seed_demo_data.py
```

Run from:

```text
services/api
```

Command:

```bash
DATABASE_URL="postgresql://retailops:retailops@localhost:5432/retailops" python scripts/seed_demo_data.py
```

Expected seed summary:

```text
Seed summary:
- products: 8
- users: 4
- sales: 8
- inventory_snapshots: 6
- forecasts: 4
- anomalies: 4
- alerts: 4
- recommendations: 4
- workflow_actions: 4

Demo seed data inserted successfully.
```

## Demo Data Characteristics

The seed data intentionally includes a small but realistic set of retail scenarios:

| Scenario | Example |
|---|---|
| Normal sales activity | Products with sales records and no anomalies. |
| Sales drop | Organic Milk sales dropped below expected demand. |
| Stockout risk | Winter Jacket stockout risk after demand spike. |
| Pricing review | Wireless Headphones price may be below market pattern. |
| Stale inventory | Oak Floor Panels inventory is stale. |
| Operational workflow | Alerts assigned to users and moved through workflow actions. |
| Recommendations | Suggested actions such as replenish stock, review price, or refresh inventory data. |

## Validation Queries

### Product Data Coverage

```sql
SELECT
    p.sku,
    p.name,
    COUNT(s.id) AS sales_rows,
    COUNT(f.id) AS forecast_rows,
    COUNT(a.id) AS anomaly_rows
FROM products p
LEFT JOIN sales s ON s.product_id = p.id
LEFT JOIN forecasts f ON f.product_id = p.id
LEFT JOIN anomalies a ON a.product_id = p.id
GROUP BY p.sku, p.name
ORDER BY p.sku;
```

This query verifies that products are connected to sales, forecasts, and anomalies.

### Alerts Overview

```sql
SELECT
    al.title,
    al.severity,
    al.status,
    p.name AS product_name,
    u.display_name AS assigned_to
FROM alerts al
JOIN products p ON p.id = al.product_id
LEFT JOIN users u ON u.id = al.assigned_to_user_id
ORDER BY al.severity DESC, al.created_at DESC;
```

This query verifies that alerts are connected to products and assigned users.

### Recommendations Overview

```sql
SELECT
    r.recommendation_type,
    r.status,
    p.name AS product_name,
    r.recommended_action
FROM recommendations r
JOIN products p ON p.id = r.product_id
ORDER BY r.generated_at DESC;
```

This query verifies that recommendations are connected to products and contain meaningful business actions.

## Tests

The current test suite validates the database and application basics.

Run all backend tests from `services/api`:

```bash
pytest
```

Current expected result:

```text
14 passed
```

Relevant test files:

| Test file | Purpose |
|---|---|
| `tests/test_database_schema.py` | Validates database schema assumptions. |
| `tests/test_seed_data.py` | Validates demo seed data integrity. |
| `tests/test_domain_models.py` | Validates Pydantic/domain model behavior. |
| `tests/test_health.py` | Validates basic health endpoint behavior. |
| `tests/test_readiness.py` | Validates readiness checks. |
| `tests/test_errors.py` | Validates error response behavior. |

## Local Development Requirements

Before running migrations or seed scripts, the local PostgreSQL container must be running.

Typical local setup:

```bash
docker compose up --build
```

Then from `services/api`:

```bash
python -m alembic upgrade head
DATABASE_URL="postgresql://retailops:retailops@localhost:5432/retailops" python scripts/seed_demo_data.py
pytest
```

## Troubleshooting

### Problem: database connection fails

Check that Docker Compose is running:

```bash
docker ps
```

Check that the database container exists and is healthy.

### Problem: Alembic cannot connect to PostgreSQL

Make sure `DATABASE_URL` points to the local PostgreSQL database:

```bash
export DATABASE_URL="postgresql://retailops:retailops@localhost:5432/retailops"
```

Then run:

```bash
python -m alembic upgrade head
```

### Problem: table does not exist

Apply migrations again:

```bash
python -m alembic upgrade head
```

Then inspect tables:

```bash
docker exec -it retailops-cloud-native-platform-db-1 psql -U retailops -d retailops -c "\\dt"
```

### Problem: seed script inserts duplicate data

The seed script should be safe to run repeatedly if it uses stable unique identifiers such as SKUs and logins, or if it clears/reuses existing demo records intentionally.

After rerunning the seed script, run:

```bash
pytest
```
