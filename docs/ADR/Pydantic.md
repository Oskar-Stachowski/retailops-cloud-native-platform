# Decision:
Use Pydantic models for the first RetailOps MVP domain model.

# Context:
The API is still in early MVP stage. We need clear data contracts for products,
sales, inventory, alerts, forecasts, anomalies, recommendations and workflow actions.

# Options considered:
1. dataclasses
2. Pydantic models
3. SQLAlchemy models

# Decision:
Choose Pydantic for Sprint 3 domain modeling.

# Rationale:
Pydantic integrates naturally with FastAPI, supports validation, produces clean
schemas, and can later be mapped to database models when PostgreSQL and migrations
are introduced.

# Consequence:
The first model is not yet the database schema. SQLAlchemy/Alembic will come later.