# Decision:
Use PostgreSQL as the primary relational database for the RetailOps MVP.

# Context:
RetailOps needs a reliable transactional database for products, sales, inventory snapshots, forecasts, anomalies, alerts, recommendations and workflow actions.

The data model contains relationships, foreign keys, constraints, timestamps and realistic operational records. The database must support repeatable migrations, seed data and future analytics-oriented API endpoints.

# Options considered:
1. SQLite for local-only development
2. MySQL / MariaDB
3. PostgreSQL
4. NoSQL document database
5. In-memory demo storage

# Decision:
Choose PostgreSQL as the primary database for the RetailOps MVP.

# Rationale:
PostgreSQL is a strong default choice for cloud-native business applications that need relational integrity, transactional consistency and mature ecosystem support.

It supports foreign keys, check constraints, indexes, UUIDs, timestamps and realistic operational data modeling.

PostgreSQL also fits well with the future project direction:
- API query layer
- dashboard endpoints
- analytics queries
- Kubernetes deployments
- Terraform-managed cloud infrastructure
- production-like observability and backup practices

# Consequence:
The RetailOps MVP uses PostgreSQL as the source of truth for operational demo data.

The project must maintain database migrations, schema constraints and seed data compatibility.

The trade-off is slightly more setup complexity than SQLite, but this is acceptable because the project is intended to demonstrate production-style DevOps and cloud-native engineering practices.