# Decision:
Use Alembic for PostgreSQL database migrations.

# Context:
The RetailOps API needs a repeatable way to create and evolve the database schema.

The project already contains multiple related tables, including products, users, sales, inventory snapshots, forecasts, anomalies, alerts, recommendations and workflow actions.

Manual schema changes would be risky because the database must work consistently across local development, CI and future cloud environments.

# Options considered:
1. Manual SQL scripts
2. SQLAlchemy create_all()
3. Alembic migrations
4. Rebuilding the database manually during development
5. Keeping schema only in documentation

# Decision:
Choose Alembic as the database migration tool.

# Rationale:
Alembic gives the project a versioned and repeatable database migration mechanism.

This allows us to create the same schema across environments using:

alembic upgrade head

It also fits naturally with CI/CD because schema setup can be automated before tests and seed loading.

Alembic supports controlled schema evolution, which will become important when the RetailOps data model grows in future sprints.

# Consequence:
Database schema changes should be introduced through migration files.

The project gains a clear lifecycle:

migration file -> alembic upgrade head -> PostgreSQL schema -> seed data -> tests

The trade-off is that developers must understand migration discipline. Changing an already-applied migration can be acceptable during very early local MVP work, but later changes should be added as new migration revisions.