ROOT_DIR := ../..
DATABASE_URL ?= postgresql://retailops:retailops@localhost:5432/retailops
PYTHONPATH ?= .

.PHONY: migrate seed test generate-demo reset-db demo-refresh


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