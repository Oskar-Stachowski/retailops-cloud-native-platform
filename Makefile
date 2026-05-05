SHELL := /bin/bash

API_DIR := services/api
FRONTEND_DIR := frontend

-include .env

POSTGRES_DB ?= retailops
POSTGRES_USER ?= retailops
POSTGRES_PASSWORD ?= retailops
POSTGRES_PORT ?= 5432
DATABASE_URL ?= postgresql://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@localhost:$(POSTGRES_PORT)/$(POSTGRES_DB)

.PHONY: help \
	test api-test api-integration-test frontend-test frontend-lint frontend-build \
	data-generate api-migrate api-seed api-demo-refresh \
	compose-config compose-up compose-down compose-ps compose-logs compose-smoke compose-rebuild-smoke

help:
	@printf "RetailOps platform commands\n\n"
	@printf "Quality gates:\n"
	@printf "  make test                  Run API unit, API DB integration, and frontend tests\n"
	@printf "  make api-test              Run API tests that do not require a database\n"
	@printf "  make api-integration-test  Prepare Compose DB and run API DB integration tests\n"
	@printf "  make frontend-test         Run frontend tests\n"
	@printf "  make frontend-lint         Run frontend lint\n"
	@printf "  make frontend-build        Build frontend production assets\n\n"
	@printf "Data and database:\n"
	@printf "  make data-generate         Generate demo CSV data\n"
	@printf "  make api-migrate           Run Alembic migrations against DATABASE_URL\n"
	@printf "  make api-seed              Seed demo data against DATABASE_URL\n"
	@printf "  make api-demo-refresh      Generate data, migrate, and seed\n\n"
	@printf "Docker Compose runtime:\n"
	@printf "  make compose-config        Render Docker Compose config\n"
	@printf "  make compose-up            Build and start local stack\n"
	@printf "  make compose-down          Stop local stack\n"
	@printf "  make compose-ps            Show local stack status\n"
	@printf "  make compose-logs          Follow local stack logs\n"
	@printf "  make compose-smoke         Run smoke checks against running stack\n"
	@printf "  make compose-rebuild-smoke Build, start, and smoke test local stack\n"

test: api-test api-integration-test frontend-test

api-test:
	cd $(API_DIR) && PYTHONPATH=. pytest -m "not integration_db"

api-integration-test:
	docker compose up --build -d seed
	cd $(API_DIR) && PYTHONPATH=. DATABASE_URL=$(DATABASE_URL) REQUIRE_DB_TESTS=1 pytest -m integration_db

frontend-test:
	cd $(FRONTEND_DIR) && npm test

frontend-lint:
	cd $(FRONTEND_DIR) && npm run lint --if-present

frontend-build:
	cd $(FRONTEND_DIR) && npm run build

data-generate:
	python -m data.generator.main

api-migrate:
	cd $(API_DIR) && DATABASE_URL=$(DATABASE_URL) alembic upgrade head

api-seed:
	cd $(API_DIR) && PYTHONPATH=. DATABASE_URL=$(DATABASE_URL) python scripts/seed_demo_data.py

api-demo-refresh: data-generate api-migrate api-seed

compose-config:
	docker compose config

compose-up:
	docker compose up --build -d

compose-down:
	docker compose down

compose-ps:
	docker compose ps -a

compose-logs:
	docker compose logs -f

compose-smoke:
	./scripts/compose_smoke.sh

compose-rebuild-smoke: compose-up compose-smoke
