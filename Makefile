# RetailOps root Makefile
# Purpose:
# - local developer preflight
# - shared command layer for GitHub Actions and Jenkins
# - local-first CI/CD foundation before AWS/ECR/EKS exists

SHELL := /bin/bash

# Local-only convenience. Do not commit real secrets in .env.
-include .env

COMPOSE ?= docker compose
PYTHON ?= python
PIP ?= pip
NPM ?= npm

API_DIR ?= services/api
FRONTEND_DIR ?= frontend
REPORTS_DIR ?= ci-cd/reports
SECURITY_REPORTS_DIR ?= $(REPORTS_DIR)/security

POSTGRES_DB ?= retailops
POSTGRES_USER ?= retailops_local
POSTGRES_PASSWORD ?= retailops_local_dev_password
POSTGRES_PORT ?= 5432

API_PORT ?= 8000
FRONTEND_PORT ?= 3000
APP_ENV ?= local

DATABASE_URL ?= postgresql://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@localhost:$(POSTGRES_PORT)/$(POSTGRES_DB)

API_IMAGE ?= retailops-api:local
FRONTEND_IMAGE ?= retailops-frontend:local

SMOKE_SCRIPT ?= ./scripts/compose_smoke.sh

export POSTGRES_DB
export POSTGRES_USER
export POSTGRES_PASSWORD
export POSTGRES_PORT
export API_PORT
export FRONTEND_PORT
export APP_ENV
export DATABASE_URL

.PHONY: help
help:
	@echo "RetailOps root Makefile"
	@echo ""
	@echo "Local quality:"
	@echo "  make install              Install backend and frontend dependencies"
	@echo "  make ci-local             Run local preflight without full Compose smoke"
	@echo "  make test                 Run backend and frontend tests"
	@echo ""
	@echo "Backend:"
	@echo "  make api-install          Install backend dependencies"
	@echo "  make api-test             Run backend pytest"
	@echo "  make api-integration-test Run DB-backed backend checks using local Compose DB"
	@echo "  make api-migrate          Run Alembic migrations"
	@echo "  make api-seed             Seed demo data"
	@echo ""
	@echo "Frontend:"
	@echo "  make frontend-install     Install frontend dependencies"
	@echo "  make frontend-test        Run frontend tests"
	@echo "  make frontend-lint        Run frontend lint"
	@echo "  make frontend-build       Build frontend"
	@echo ""
	@echo "Docker / Compose:"
	@echo "  make docker-build         Build backend and frontend images"
	@echo "  make compose-config       Validate Docker Compose config"
	@echo "  make compose-up           Start full local stack"
	@echo "  make compose-smoke        Run local smoke test against running stack"
	@echo "  make compose-ci           Build, start, smoke-test, log on failure, cleanup"
	@echo "  make compose-down         Stop and remove local stack"
	@echo ""
	@echo "Security:"
	@echo "  make security-scan        Run local secret, filesystem and image scans"
	@echo ""

.PHONY: ensure-reports-dir
ensure-reports-dir:
	@mkdir -p "$(REPORTS_DIR)" "$(SECURITY_REPORTS_DIR)"

# -------------------------------------------------------------------
# Dependency installation
# -------------------------------------------------------------------

.PHONY: install api-install frontend-install
install: api-install frontend-install

api-install:
	cd "$(API_DIR)" && "$(PIP)" install -r requirements.txt

frontend-install:
	cd "$(FRONTEND_DIR)" && "$(NPM)" ci

# -------------------------------------------------------------------
# Backend
# -------------------------------------------------------------------

.PHONY: api-test api-integration-test api-migrate api-seed data-generate db-up db-down

api-test:
	cd "$(API_DIR)" && PYTHONPATH=. DATABASE_URL="$(DATABASE_URL)" pytest

db-up:
	$(COMPOSE) up -d db

db-down:
	$(COMPOSE) down -v --remove-orphans

data-generate:
	$(PYTHON) -m data.generator.main

api-migrate:
	cd "$(API_DIR)" && PYTHONPATH=. DATABASE_URL="$(DATABASE_URL)" alembic upgrade head

api-seed:
	cd "$(API_DIR)" && PYTHONPATH=. DATABASE_URL="$(DATABASE_URL)" python scripts/seed_demo_data.py

api-integration-test: db-up data-generate api-migrate api-seed
	cd "$(API_DIR)" && PYTHONPATH=. DATABASE_URL="$(DATABASE_URL)" REQUIRE_DB_TESTS=1 pytest

# -------------------------------------------------------------------
# Frontend
# -------------------------------------------------------------------

.PHONY: frontend-test frontend-lint frontend-build

frontend-test:
	cd "$(FRONTEND_DIR)" && "$(NPM)" test

frontend-lint:
	cd "$(FRONTEND_DIR)" && "$(NPM)" run lint

frontend-build:
	cd "$(FRONTEND_DIR)" && "$(NPM)" run build

# -------------------------------------------------------------------
# Local CI / developer preflight
# -------------------------------------------------------------------

.PHONY: test ci-local

test: api-test frontend-test

ci-local: compose-config api-test frontend-test frontend-lint frontend-build
	@echo "Local CI preflight passed."

# -------------------------------------------------------------------
# Docker / Compose
# -------------------------------------------------------------------

.PHONY: docker-build compose-config compose-up compose-down compose-logs compose-smoke compose-rebuild-smoke compose-ci

docker-build:
	docker build -t "$(API_IMAGE)" "$(API_DIR)"
	docker build -t "$(FRONTEND_IMAGE)" "$(FRONTEND_DIR)"

compose-config:
	$(COMPOSE) config

compose-up:
	$(COMPOSE) up --build -d

compose-down:
	$(COMPOSE) down -v --remove-orphans

compose-logs:
	$(COMPOSE) logs --no-color

compose-smoke:
	chmod +x "$(SMOKE_SCRIPT)"
	API_BASE_URL="http://localhost:$(API_PORT)" FRONTEND_BASE_URL="http://localhost:$(FRONTEND_PORT)" "$(SMOKE_SCRIPT)"

compose-rebuild-smoke: compose-ci

compose-ci: ensure-reports-dir
	@set -e; \
	status=0; \
	echo "[compose-ci] Cleaning previous Compose state..."; \
	$(COMPOSE) down -v --remove-orphans >/dev/null 2>&1 || true; \
	echo "[compose-ci] Validating Compose config..."; \
	$(COMPOSE) config; \
	echo "[compose-ci] Starting full RetailOps stack..."; \
	$(COMPOSE) up --build -d || status=$$?; \
	if [[ $$status -eq 0 ]]; then \
		echo "[compose-ci] Running smoke tests..."; \
		chmod +x "$(SMOKE_SCRIPT)"; \
		API_BASE_URL="http://localhost:$(API_PORT)" FRONTEND_BASE_URL="http://localhost:$(FRONTEND_PORT)" "$(SMOKE_SCRIPT)" || status=$$?; \
	fi; \
	$(COMPOSE) ps > "$(REPORTS_DIR)/docker-compose-ps.txt" || true; \
	if [[ $$status -ne 0 ]]; then \
		echo "[compose-ci] Failure detected. Capturing Compose logs..."; \
		$(COMPOSE) logs --no-color > "$(REPORTS_DIR)/docker-compose-logs.txt" || true; \
		cat "$(REPORTS_DIR)/docker-compose-logs.txt" || true; \
	fi; \
	echo "[compose-ci] Cleaning Compose stack..."; \
	$(COMPOSE) down -v --remove-orphans || true; \
	exit $$status

# -------------------------------------------------------------------
# Security scans
# These are local/Jenkins helpers. GitHub Actions also runs security-ci.yml.
# -------------------------------------------------------------------

.PHONY: check-trivy check-gitleaks secret-scan security-fs-scan security-image-scan security-scan

check-trivy:
	@command -v trivy >/dev/null 2>&1 || { \
		echo "ERROR: trivy is not installed. Install Trivy or run GitHub Actions security-ci."; \
		exit 1; \
	}

check-gitleaks:
	@command -v gitleaks >/dev/null 2>&1 || { \
		echo "ERROR: gitleaks is not installed. Install Gitleaks or run GitHub Actions security-ci."; \
		exit 1; \
	}

secret-scan: check-gitleaks ensure-reports-dir
	gitleaks detect --source . --redact --verbose --report-format json --report-path "$(SECURITY_REPORTS_DIR)/gitleaks.json"

security-fs-scan: check-trivy ensure-reports-dir
	trivy fs \
		--severity CRITICAL,HIGH \
		--ignore-unfixed \
		--exit-code 1 \
		--format table \
		--output "$(SECURITY_REPORTS_DIR)/trivy-fs.txt" \
		.

security-image-scan: check-trivy ensure-reports-dir docker-build
	trivy image \
		--severity CRITICAL \
		--ignore-unfixed \
		--exit-code 1 \
		--format table \
		--output "$(SECURITY_REPORTS_DIR)/trivy-api-image.txt" \
		"$(API_IMAGE)"
	trivy image \
		--severity CRITICAL \
		--ignore-unfixed \
		--exit-code 1 \
		--format table \
		--output "$(SECURITY_REPORTS_DIR)/trivy-frontend-image.txt" \
		"$(FRONTEND_IMAGE)"

security-scan: secret-scan security-fs-scan security-image-scan
	@echo "Security scans passed."

# -------------------------------------------------------------------
# Cleanup
# -------------------------------------------------------------------

.PHONY: clean
clean:
	rm -rf "$(REPORTS_DIR)"
	$(COMPOSE) down -v --remove-orphans || true