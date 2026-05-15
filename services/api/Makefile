ROOT_DIR := ../..
DATABASE_URL ?= postgresql://retailops:retailops@localhost:5432/retailops
PYTHONPATH ?= .
RETAILOPS_SEED_DATA_PROFILE ?= small

.PHONY: help migrate seed seed-demo seed-small seed-medium test generate-demo reset-db demo-refresh

help:
	@printf "RetailOps API-local commands\n\n"
	@printf "Use the root Makefile for full-platform commands.\n\n"
	@printf "  make migrate       Run Alembic migrations against DATABASE_URL\n"
	@printf "  make seed          Seed the default local dataset profile (small)\n"
	@printf "  make seed-demo     Seed demo smoke/CI data against DATABASE_URL\n"
	@printf "  make seed-small    Seed small local portfolio data against DATABASE_URL\n"
	@printf "  make seed-medium   Seed medium showcase/performance data against DATABASE_URL\n"
	@printf "  make test          Run API tests\n"
	@printf "  make generate-demo Generate demo CSV data from repo root\n"
	@printf "  make reset-db      Recreate local Postgres volume and run migrations\n"
	@printf "  make demo-refresh  Generate data, reset DB, and seed\n"

migrate:
	DATABASE_URL=$(DATABASE_URL) alembic upgrade head

seed: seed-small

seed-demo:
	PYTHONPATH=$(PYTHONPATH) DATABASE_URL=$(DATABASE_URL) RETAILOPS_SEED_DATA_PROFILE=demo python scripts/seed_demo_data.py

seed-small:
	PYTHONPATH=$(PYTHONPATH) DATABASE_URL=$(DATABASE_URL) RETAILOPS_SEED_DATA_PROFILE=small python scripts/seed_demo_data.py

seed-medium:
	PYTHONPATH=$(PYTHONPATH) DATABASE_URL=$(DATABASE_URL) RETAILOPS_SEED_DATA_PROFILE=medium python scripts/seed_demo_data.py

test:
	PYTHONPATH=. DATABASE_URL=$(DATABASE_URL) pytest


generate-demo:
	cd $(ROOT_DIR) && python -m data.generator.main

reset-db:
	cd $(ROOT_DIR) && docker compose down -v
	cd $(ROOT_DIR) && docker compose up -d db
	sleep 3
	$(MAKE) migrate

demo-refresh: generate-demo reset-db seed
