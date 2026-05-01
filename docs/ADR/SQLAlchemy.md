# Decision:
Use SQLAlchemy Core constructs inside Alembic migrations, but defer SQLAlchemy ORM adoption for the early MVP.

# Context:
RetailOps needs database schema definitions for PostgreSQL migrations.

At the current stage, the project already uses Pydantic models for API/domain data contracts and Psycopg for direct database connectivity and seed loading.

The project does not yet have a repository/service layer that requires ORM entities.

# Options considered:
1. No SQLAlchemy usage
2. SQLAlchemy Core only for migration definitions
3. SQLAlchemy ORM for application persistence
4. Raw SQL migration files
5. Full ORM-first database model

# Decision:
Use SQLAlchemy Core schema constructs in Alembic migration files.

Do not introduce SQLAlchemy ORM yet for the application layer.

# Rationale:
Alembic migrations use SQLAlchemy constructs such as:

sa.Column(...)
sa.String(...)
sa.Integer(...)
sa.ForeignKey(...)
sa.CheckConstraint(...)

This provides a structured and readable way to define database tables, columns, constraints and indexes.

At the same time, delaying SQLAlchemy ORM keeps the MVP simpler. The current focus is on schema, migrations, seed data, tests and API readiness rather than complex persistence abstractions.

# Consequence:
SQLAlchemy is currently used as a schema definition layer for migrations, not as the main application ORM.

The project keeps a clean separation:
- Pydantic models for API/domain validation
- SQLAlchemy Core constructs for migration definitions
- Psycopg for direct PostgreSQL operations in health checks and seed scripts

In future sprints, SQLAlchemy ORM or SQLAlchemy Core query layers may be introduced when repository and service layers become necessary.