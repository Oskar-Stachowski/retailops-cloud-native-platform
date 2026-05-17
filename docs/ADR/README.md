# ADR Index

This index summarizes the architecture decision records and the one accepted IAM exception currently tracked in the repository.

`Implemented files` lists the primary code or configuration paths that currently reflect the decision. `Evidence` points to the best reviewer-facing proof or supporting document, not an exhaustive implementation inventory.

| ADR | Title | Status | Decision | Implemented files | Evidence |
|---|---|---|---|---|---|
| ADR-001 | Pydantic | Accepted | Use Pydantic models for MVP domain and API data contracts. | `services/api/app/domain/models.py`, `services/api/app/api/schemas.py` | `services/api/tests/test_domain_models.py`, `docs/api.md` |
| ADR-002 | Psycopg | Accepted | Use Psycopg for direct PostgreSQL connectivity, readiness checks, and seed loading. | `services/api/app/db/connection.py`, `services/api/scripts/seed_demo_data.py` | `services/api/tests/test_health.py`, `services/api/tests/test_seed_data.py` |
| ADR-003 | PostgreSQL | Accepted | Use PostgreSQL as the primary operational data store. | `docker-compose.yml`, `services/api/alembic/`, `data/demo/` | `services/api/tests/test_database_schema.py`, `docs/database_migrations_and_seed_data.md` |
| ADR-004 | Alembic | Accepted | Manage schema changes through Alembic migrations. | `services/api/alembic/`, `services/api/alembic.ini` | `services/api/tests/test_database_schema.py`, `docs/database_migrations_and_seed_data.md` |
| ADR-005 | SQLAlchemy | Accepted | Use SQLAlchemy Core in migrations and defer ORM adoption. | `services/api/alembic/versions/` | `docs/ADR/SQLAlchemy.md`, `services/api/tests/test_database_schema.py` |
| ADR-010 | Terraform Layout | Accepted | Use an environment-plus-modules Terraform layout for the AWS foundation. | `infra/environments/dev/main.tf`, `infra/modules/` | `ci-cd/reports/iac/sprint-10-terraform-validate.txt`, `infra/README.md` |
| ADR-011 | AWS Networking Baseline | Accepted | Use a minimal VPC baseline without NAT Gateway. | `infra/modules/vpc/`, `infra/environments/dev/main.tf` | `ci-cd/reports/iac/sprint-10-terraform-plan-dev.txt`, `docs/networking-baseline.md` |
| ADR-012 | AWS Cost Control Baseline | Accepted | Use mandatory tags, budget guardrails, short retention, and documented cleanup before larger AWS expansion. | `infra/modules/budget/`, `infra/modules/cloudwatch/`, `docs/runbooks/aws-cleanup-runbook.md` | `docs/evidence/aws/aws-cleanup-confirmation.md`, `docs/cost-monitoring.md` |
| ADR-013 | IAM Delivery Access Model | Accepted | Use least-privilege, plan-oriented IAM boundaries for future CI/CD access. | `infra/modules/iam/`, `docs/iam-baseline.md` | `ci-cd/reports/iac/sprint-10-terraform-plan-dev.txt`, `docs/ADR/terraform-plan-readonly-iam-discovery.md` |
| ADR-T01 | CI/CD Tooling Split | Draft / target maturity | Use GitHub Actions for code confidence and Jenkins for release-confidence orchestration. | `.github/workflows/`, `Jenkinsfile`, `Makefile` | `ci-cd/README.md`, `docs/evidence/jenkins/README.md` |
| EX-001 | Terraform Plan Read-Only IAM Discovery | Accepted exception | Allow broad read-only discovery actions required by Terraform plan. | `infra/modules/iam/` | `docs/ADR/terraform-plan-readonly-iam-discovery.md` |

## Usage Notes

- Use this file as the reviewer entry point for architecture decisions.
- Update the table when a new ADR is added, accepted, superseded, or tied to new implementation evidence.
- If an ADR stays aspirational, keep the status explicit and avoid listing it as implemented elsewhere in the repository.
