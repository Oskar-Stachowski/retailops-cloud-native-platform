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
REPORTS_DIR ?= ci-cd/reports
SECURITY_REPORTS_DIR ?= $(REPORTS_DIR)/security
IAC_REPORTS_DIR ?= $(REPORTS_DIR)/iac

TERRAFORM ?= terraform
INFRA_DIR ?= infra
TERRAFORM_DIR ?= $(INFRA_DIR)/environments/dev
TERRAFORM_VAR_FILE ?= terraform.tfvars.example
TERRAFORM_VALIDATE_REPORT ?= $(IAC_REPORTS_DIR)/terraform-validate.txt
TERRAFORM_PLAN_REPORT ?= $(IAC_REPORTS_DIR)/terraform-plan-dev.txt

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
	@echo "Terraform / IaC:"
	@echo "  make terraform-fmt        Format Terraform files under infra/"
	@echo "  make terraform-validate   Initialize Terraform locally and validate dev"
	@echo "  make terraform-plan-dev   Create a dev Terraform plan report"
	@echo "  make iac-scan             Run local IaC validation and safety checks"
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
# Terraform / Infrastructure as Code
# These targets are local-first helpers. They validate and collect evidence
# before Terraform is promoted to GitHub Actions or Jenkins automation.
# -------------------------------------------------------------------

.PHONY: check-terraform ensure-iac-reports-dir terraform-fmt terraform-fmt-check terraform-init-local terraform-validate terraform-plan-dev iac-secret-scan iac-scan

check-terraform:
	@command -v "$(TERRAFORM)" >/dev/null 2>&1 || { \
		echo "ERROR: terraform is not installed or not available in PATH."; \
		exit 1; \
	}

ensure-iac-reports-dir:
	@mkdir -p "$(IAC_REPORTS_DIR)"

terraform-fmt: check-terraform
	$(TERRAFORM) fmt -recursive "$(INFRA_DIR)"

terraform-fmt-check: check-terraform
	$(TERRAFORM) fmt -recursive -check -diff "$(INFRA_DIR)"

terraform-init-local: check-terraform ensure-iac-reports-dir
	$(TERRAFORM) -chdir="$(TERRAFORM_DIR)" init -backend=false -input=false

terraform-validate: terraform-init-local
	@set -o pipefail; \
	$(TERRAFORM) -chdir="$(TERRAFORM_DIR)" validate -no-color | tee "$(TERRAFORM_VALIDATE_REPORT)"

terraform-plan-dev: terraform-init-local
	@set -o pipefail; \
	$(TERRAFORM) -chdir="$(TERRAFORM_DIR)" plan \
		-var-file="$(TERRAFORM_VAR_FILE)" \
		-no-color | tee "$(TERRAFORM_PLAN_REPORT)"

iac-secret-scan: ensure-iac-reports-dir
	@echo "[iac-secret-scan] Checking Terraform/docs for obvious AWS secrets or real IAM ARNs..."
	@if grep -R -I \
		--exclude-dir=".terraform" \
		--exclude=".terraform.lock.hcl" \
		--exclude="*.png" \
		--exclude="*.jpg" \
		--exclude="*.jpeg" \
		--exclude="*.webp" \
		-E 'AKIA[0-9A-Z]{16}|arn:aws:iam::[0-9]{12}' \
		"$(INFRA_DIR)" docs; then \
		echo "ERROR: potential AWS secret or real IAM ARN found in IaC/docs."; \
		exit 1; \
	else \
		echo "[iac-secret-scan] No obvious AWS access keys or real IAM ARNs found."; \
	fi

iac-scan: terraform-fmt-check terraform-validate iac-secret-scan
	@echo "IaC scan passed. Use 'make terraform-plan-dev' separately when AWS credentials are available."

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