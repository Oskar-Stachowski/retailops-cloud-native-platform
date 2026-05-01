# Decision:
Use Psycopg as the PostgreSQL driver for API database connectivity, readiness checks and demo seed loading.

# Context:
The RetailOps API needs a direct and reliable way to connect to PostgreSQL during the early MVP stage.

At this stage, we use PostgreSQL for the first operational data model, database readiness checks, and demo seed data loading from CSV files. The application does not yet require a full ORM-based persistence layer.

# Options considered:
1. Raw PostgreSQL driver with Psycopg
2. SQLAlchemy ORM
3. SQLAlchemy Core
4. asyncpg
5. Shell-based psql scripts

# Decision:
Choose Psycopg for Sprint 3 database connectivity and seed loading.

# Rationale:
Psycopg gives us direct control over SQL execution, transactions and PostgreSQL-specific behavior.

It is simple enough for early MVP database checks and seed scripts, while still being production-relevant because it is a mature PostgreSQL driver.

For the current stage, this keeps the seed flow explicit:

data/demo/*.csv -> seed_demo_data.py -> Psycopg -> PostgreSQL

This is easier to debug than introducing ORM abstractions too early.

# Consequence:
The project uses explicit SQL for seed loading and database health checks.

This improves transparency for a junior engineer and makes database behavior easier to inspect during onboarding.

The trade-off is that SQL statements, column mappings and insert order must be maintained manually. As the project grows, repository and service layers may later use SQLAlchemy or another abstraction.