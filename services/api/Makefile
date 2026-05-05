ROOT_DIR := ../..
DATABASE_URL ?= postgresql://retailops:retailops@localhost:5432/retailops
PYTHONPATH ?= .

.PHONY: help migrate seed test generate-demo reset-db demo-refresh

help:
	@printf "RetailOps API-local commands\n\n"
	@printf "Use the root Makefile for full-platform commands.\n\n"
	@printf "  make migrate       Run Alembic migrations against DATABASE_URL\n"
	@printf "  make seed          Seed demo data against DATABASE_URL\n"
	@printf "  make test          Run API tests\n"
	@printf "  make generate-demo Generate demo CSV data from repo root\n"
	@printf "  make reset-db      Recreate local Postgres volume and run migrations\n"
	@printf "  make demo-refresh  Generate data, reset DB, and seed\n"

migrate:
	DATABASE_URL=$(DATABASE_URL) alembic upgrade head

seed:
	PYTHONPATH=$(PYTHONPATH) DATABASE_URL=$(DATABASE_URL) python scripts/seed_demo_data.py

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
