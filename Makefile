# RetailOps root Makefile
# Purpose:
# - local developer preflight
# - shared command layer for GitHub Actions and Jenkins
# - local-first CI/CD foundation before AWS/ECR/EKS exists

SHELL := /bin/bash

# Local-only convenience. Do not commit real secrets in .env.
-include .env

COMPOSE ?= docker compose

PYTHON ?= python3.11
API_VENV_DIR ?= $(API_DIR)/.venv
API_VENV_PYTHON ?= $(API_VENV_DIR)/bin/python
API_VENV_PIP ?= $(API_VENV_PYTHON) -m pip

NPM ?= npm

API_DIR ?= services/api
FRONTEND_DIR ?= frontend
INFRA_DIR ?= infra
INFRA_ENV ?= dev
INFRA_ENV_DIR ?= $(INFRA_DIR)/environments/$(INFRA_ENV)
REPORTS_DIR ?= ci-cd/reports
SECURITY_REPORTS_DIR ?= $(REPORTS_DIR)/security
IAC_REPORTS_DIR ?= $(REPORTS_DIR)/iac

TERRAFORM ?= terraform

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
	@echo "Infrastructure / Terraform:"
	@echo "  make terraform-fmt        Format Terraform files for the selected environment"
	@echo "  make terraform-fmt-check  Check Terraform formatting without modifying files"
	@echo "  make terraform-init       Initialize Terraform locally with backend disabled"
	@echo "  make terraform-validate   Validate Terraform configuration locally"
	@echo "  make terraform-check      Run Terraform fmt check, init, and validate"
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
	@mkdir -p "$(REPORTS_DIR)" "$(SECURITY_REPORTS_DIR)" "$(IAC_REPORTS_DIR)"

# -------------------------------------------------------------------
# Dependency installation
# -------------------------------------------------------------------

.PHONY: install api-venv api-install frontend-install
install: api-install frontend-install

api-venv:
	$(PYTHON) -m venv "$(API_VENV_DIR)"
	$(API_VENV_PYTHON) -m pip install --upgrade pip

api-install: api-venv
	$(API_VENV_PIP) install -r "$(API_DIR)/requirements.txt"

frontend-install:
	cd "$(FRONTEND_DIR)" && "$(NPM)" ci

# -------------------------------------------------------------------
# Backend
# -------------------------------------------------------------------

.PHONY: api-test api-integration-test api-migrate api-seed data-generate db-up db-down

api-test: api-install
	cd "$(API_DIR)" && PYTHONPATH=. DATABASE_URL="$(DATABASE_URL)" .venv/bin/python -m pytest

db-up:
	$(COMPOSE) up -d db

db-down:
	$(COMPOSE) down -v --remove-orphans

data-generate: api-install
	$(API_VENV_PYTHON) -m data.generator.main

api-migrate: api-install
	cd "$(API_DIR)" && PYTHONPATH=. DATABASE_URL="$(DATABASE_URL)" .venv/bin/python -m alembic upgrade head

api-seed: api-install
	cd "$(API_DIR)" && PYTHONPATH=. DATABASE_URL="$(DATABASE_URL)" .venv/bin/python scripts/seed_demo_data.py

api-integration-test: api-install db-up data-generate api-migrate api-seed
	cd "$(API_DIR)" && PYTHONPATH=. DATABASE_URL="$(DATABASE_URL)" REQUIRE_DB_TESTS=1 .venv/bin/python -m pytest

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
# Infrastructure / Terraform
# Commit 1 intentionally validates scaffold only:
# - no terraform apply
# - no AWS resources
# - no GitHub Actions infrastructure workflow yet
# -------------------------------------------------------------------

.PHONY: terraform-fmt terraform-fmt-check terraform-init terraform-validate terraform-check terraform-validate-report

terraform-fmt:
	$(TERRAFORM) -chdir="$(INFRA_ENV_DIR)" fmt -recursive

terraform-fmt-check:
	$(TERRAFORM) -chdir="$(INFRA_ENV_DIR)" fmt -recursive -check

terraform-init:
	$(TERRAFORM) -chdir="$(INFRA_ENV_DIR)" init -backend=false

terraform-validate: terraform-init
	$(TERRAFORM) -chdir="$(INFRA_ENV_DIR)" validate

terraform-check: terraform-fmt-check terraform-validate
	@echo "Terraform local checks passed for $(INFRA_ENV_DIR)."

terraform-validate-report: ensure-reports-dir terraform-init
	@set -o pipefail; \
	$(TERRAFORM) -chdir="$(INFRA_ENV_DIR)" validate -no-color | tee "$(IAC_REPORTS_DIR)/terraform-validate.txt"

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
