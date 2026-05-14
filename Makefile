# RetailOps root Makefile
# Purpose:
# - local developer preflight
# - shared command layer for GitHub Actions and Jenkins
# - local-first CI/CD foundation before AWS/ECR/EKS exists

SHELL := /bin/bash

ROOT_DIR ?= $(patsubst %/,%,$(dir $(abspath $(lastword $(MAKEFILE_LIST)))))

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
API_REPORTS_DIR ?= $(REPORTS_DIR)/api
SECURITY_REPORTS_DIR ?= $(REPORTS_DIR)/security
IAC_REPORTS_DIR ?= $(REPORTS_DIR)/iac
DATA_REPORTS_DIR ?= $(REPORTS_DIR)/data
OBSERVABILITY_REPORTS_DIR ?= $(REPORTS_DIR)/observability
PERFORMANCE_REPORTS_DIR ?= $(REPORTS_DIR)/performance
API_REQUIREMENTS ?= $(API_DIR)/requirements.txt
API_DEV_REQUIREMENTS ?= $(API_DIR)/requirements-dev.txt
API_COVERAGE_XML ?= $(API_REPORTS_DIR)/coverage.xml
API_BANDIT_REPORT ?= $(SECURITY_REPORTS_DIR)/bandit-api.txt

TERRAFORM ?= terraform
TFLINT ?= tflint
CHECKOV ?= checkov
MYPY ?= mypy
BANDIT ?= bandit
K6 ?= k6
K6_API_SMOKE_SCRIPT ?= tests/performance/k6/api-smoke.js
K6_API_SMOKE_TEXT_REPORT ?= $(PERFORMANCE_REPORTS_DIR)/api-smoke.txt
K6_API_SMOKE_SUMMARY_REPORT ?= $(PERFORMANCE_REPORTS_DIR)/api-smoke-summary.json

INFRA_DIR ?= infra
TERRAFORM_DIR ?= $(INFRA_DIR)/environments/dev
TERRAFORM_VAR_FILE ?= terraform.tfvars.example

TFLINT_CONFIG ?= $(ROOT_DIR)/security/iac/tflint.hcl
CHECKOV_CONFIG ?= $(ROOT_DIR)/security/iac/checkov.yml

TERRAFORM_VALIDATE_REPORT ?= $(IAC_REPORTS_DIR)/terraform-validate.txt
TERRAFORM_PLAN_REPORT ?= $(IAC_REPORTS_DIR)/terraform-plan-dev.txt
TFLINT_REPORT ?= $(IAC_REPORTS_DIR)/tflint.txt
CHECKOV_REPORT ?= $(IAC_REPORTS_DIR)/checkov.txt
CHECKOV_JSON_REPORT ?= $(IAC_REPORTS_DIR)/checkov.json

POSTGRES_DB ?= retailops
POSTGRES_USER ?= retailops_local
POSTGRES_PASSWORD ?= retailops_local_dev_password
POSTGRES_PORT ?= 5432
REDPANDA_KAFKA_PORT ?= 19092
REDPANDA_ADMIN_PORT ?= 19644
PROMETHEUS_PORT ?= 9090
GRAFANA_PORT ?= 3001

API_PORT ?= 8000
FRONTEND_PORT ?= 3000
APP_ENV ?= local

DATABASE_URL ?= postgresql://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@localhost:$(POSTGRES_PORT)/$(POSTGRES_DB)
RETAILOPS_BROKER_BOOTSTRAP_SERVERS ?= localhost:$(REDPANDA_KAFKA_PORT)

API_IMAGE ?= retailops-api:local
FRONTEND_IMAGE ?= retailops-frontend:local

SMOKE_SCRIPT ?= ./scripts/ci/compose_smoke.sh
STREAMING_SMOKE_SCRIPT ?= ./scripts/ci/streaming_smoke.sh
OBSERVABILITY_SMOKE_SCRIPT ?= ./scripts/ci/observability_smoke.sh
OBSERVABILITY_DEMO_TRAFFIC_SCRIPT ?= ./scripts/dev/observability_demo_traffic.sh
KUBERNETES_SMOKE_SCRIPT ?= ./scripts/ci/kubernetes_smoke.sh

DATA_PROFILE ?= small
DATA_OUTPUT_DIR ?= $(DATA_REPORTS_DIR)/generated/$(DATA_PROFILE)
DATA_QUALITY_REPORT ?= $(DATA_OUTPUT_DIR)/quality_report.json
DATA_MANIFEST_REPORT ?= $(DATA_OUTPUT_DIR)/dataset_manifest.json
DATA_REALISM_REPORT ?= $(DATA_OUTPUT_DIR)/realism_report.json
DATA_CONTRACT ?= data/contracts/retailops_seed_dataset.contract.json
EVENT_CONTRACT ?= events/contracts/retailops-realtime-events.v1.contract.json
DATA_CONTRACT_REPORT ?= $(DATA_REPORTS_DIR)/data-contract-report.json
SCENARIO_COVERAGE_REPORT ?= $(DATA_REPORTS_DIR)/scenario-coverage-report.json
SCENARIO_COVERAGE_MARKDOWN ?= docs/evidence/data/scenario-coverage-report.md
DB_BACKUP_DIR ?= $(REPORTS_DIR)/db/backups
DB_BACKUP_FILE ?=
DB_SERVICE ?= db

ML_FEATURE_PROFILE ?= small
ML_FEATURE_OUTPUT_DIR ?= data/synthetic/$(ML_FEATURE_PROFILE)/features/demand_forecast
ML_BASELINE_PROFILE ?= small
ML_BASELINE_OUTPUT_DIR ?= data/synthetic/$(ML_BASELINE_PROFILE)/models/demand_baseline
ML_BASELINE_WINDOW_DAYS ?= 28
ML_BASELINE_HORIZON_DAYS ?= 7
ML_TRAINED_PROFILE ?= small
ML_TRAINED_OUTPUT_DIR ?= data/synthetic/$(ML_TRAINED_PROFILE)/models/demand_random_forest
ML_TRAINED_WINDOW_DAYS ?= 28
ML_TRAINED_HORIZON_DAYS ?= 7
ML_TRAINED_HOLDOUT_DAYS ?= 7
ML_TRAINED_N_ESTIMATORS ?= 80
ML_EVALUATION_PROFILE ?= small
ML_EVALUATION_OUTPUT_DIR ?= data/synthetic/$(ML_EVALUATION_PROFILE)/reports/demand_baseline
ML_EVALUATION_WINDOW_DAYS ?= 28
ML_EVALUATION_HOLDOUT_DAYS ?= 7
ML_METADATA_PROFILE ?= small
ML_METADATA_OUTPUT_DIR ?= data/synthetic/$(ML_METADATA_PROFILE)/metadata/model_registry
ML_METADATA_STATUS ?= experimental
ML_INFERENCE_PROFILE ?= small
ML_INFERENCE_OUTPUT_DIR ?= data/synthetic/$(ML_INFERENCE_PROFILE)/inference/demand_baseline
ML_INFERENCE_WINDOW_DAYS ?= 28
ML_INFERENCE_HORIZON_DAYS ?= 7
ML_INFERENCE_HOLDOUT_DAYS ?= 7
ML_INFERENCE_MODEL_STATUS ?= candidate
ML_METRICS_PROFILE ?= small
ML_METRICS_OUTPUT_DIR ?= data/synthetic/$(ML_METRICS_PROFILE)/observability/model_performance
ML_METRICS_WINDOW_DAYS ?= 28
ML_METRICS_HORIZON_DAYS ?= 7
ML_METRICS_HOLDOUT_DAYS ?= 7
ML_METRICS_MODEL_STATUS ?= candidate
ML_DRIFT_PROFILE ?= small
ML_DRIFT_OUTPUT_DIR ?= data/synthetic/$(ML_DRIFT_PROFILE)/reports/demand_feature_drift
ML_DRIFT_REFERENCE_SEED ?= 42
ML_DRIFT_CURRENT_SEED ?= 43
ML_DRIFT_WARNING_THRESHOLD ?= 0.1000
ML_DRIFT_FAILURE_THRESHOLD ?= 0.2500

export POSTGRES_DB
export POSTGRES_USER
export POSTGRES_PASSWORD
export POSTGRES_PORT
export REDPANDA_KAFKA_PORT
export REDPANDA_ADMIN_PORT
export PROMETHEUS_PORT
export GRAFANA_PORT
export API_PORT
export FRONTEND_PORT
export APP_ENV
export DATABASE_URL
export RETAILOPS_BROKER_BOOTSTRAP_SERVERS

.PHONY: help
help:
	@echo "RetailOps root Makefile"
	@echo ""
	@echo "Local quality:"
	@echo "  make install              Install backend and frontend dependencies"
	@echo "  make ci-local             Run local preflight without full Compose smoke"
	@echo "  make test                 Run backend and frontend tests"
	@echo "  make data-quality         Generate synthetic data and validate quality report"
	@echo "  make data-contracts       Validate demo CSVs and event schema against data contracts"
	@echo "  make data-scenario-report Generate scenario coverage evidence"
	@echo "  make db-backup            Create local PostgreSQL logical backup evidence"
	@echo "  make db-restore           Restore local PostgreSQL backup evidence"
	@echo "  make ml-features          Generate demand forecasting feature dataset"
	@echo "  make ml-baseline          Train baseline demand forecasting model"
	@echo "  make ml-trained           Train RandomForest demand forecasting model"
	@echo "  make ml-evaluate          Generate baseline model evaluation report"
	@echo "  make ml-metadata          Persist baseline model metadata locally"
	@echo "  make ml-inference         Run batch demand forecast inference"
	@echo "  make ml-metrics           Generate model performance metrics artifacts"
	@echo "  make ml-drift             Generate demand feature drift checks"
	@echo ""
	@echo "Backend:"
	@echo "  make api-install          Install backend dependencies"
	@echo "  make api-lint             Run Ruff backend/data checks"
	@echo "  make api-format-check     Check Ruff formatting"
	@echo "  make api-type-check       Run mypy against the curated typed backend modules"
	@echo "  make api-security-lint    Generate a report-only Bandit scan for backend application and script code"
	@echo "  make api-coverage         Run backend pytest with coverage gate"
	@echo "  make api-test             Run backend pytest"
	@echo "  make api-integration-test Run DB-backed backend checks using local Compose DB"
	@echo "  make performance-smoke    Run k6 API smoke baseline and save p95 evidence"
	@echo "  make pre-commit-run       Run configured pre-commit hooks against all files"
	@echo "  make api-migrate          Run Alembic migrations"
	@echo "  make api-seed             Seed demo data"
	@echo "  make db-readiness-evidence Run data readiness evidence gates"
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
	@echo "  make tflint-report        Run TFLint only against infra/ and save report"
	@echo "  make checkov-scan         Run Checkov report-only IaC scan"
	@echo "  make iac-scan             Run Terraform validation, guardrails, TFLint and Checkov"
	@echo "  make k8s-smoke            Render and validate Kubernetes base/dev manifests"
	@echo ""
	@echo "Docker / Compose:"
	@echo "  make docker-build         Build backend and frontend images"
	@echo "  make compose-config       Validate Docker Compose config"
	@echo "  make compose-up           Start full local stack"
	@echo "  make broker-up            Start local Redpanda broker and create topics"
	@echo "  make broker-topics        List local Redpanda topics"
	@echo "  make realtime-consumer    Run local long-running realtime consumer"
	@echo "  make observability-up     Start API, Prometheus and Grafana for local metrics"
	@echo "  make observability-smoke  Validate API metrics, Prometheus and Grafana"
	@echo "  make observability-demo-traffic Generate demo observability traffic and stream metrics"
	@echo "  make compose-smoke        Run local smoke test against running stack"
	@echo "  make streaming-smoke      Run streaming smoke test against broker/API/Prometheus"
	@echo "  make compose-ci           Build, start, smoke-test, log on failure, cleanup"
	@echo "  make compose-down         Stop and remove local stack"
	@echo ""
	@echo "Security:"
	@echo "  make security-scan        Run local secret, filesystem and image scans"
	@echo ""


.PHONY: ensure-reports-dir
ensure-reports-dir:
	@mkdir -p "$(REPORTS_DIR)" "$(API_REPORTS_DIR)" "$(SECURITY_REPORTS_DIR)" "$(IAC_REPORTS_DIR)" "$(DATA_REPORTS_DIR)" "$(OBSERVABILITY_REPORTS_DIR)" "$(PERFORMANCE_REPORTS_DIR)" "$(REPORTS_DIR)/k8s" "$(DB_BACKUP_DIR)"

# -------------------------------------------------------------------
# Dependency installation
# -------------------------------------------------------------------

.PHONY: install api-venv api-install frontend-install pre-commit-install pre-commit-run
install: api-install frontend-install

api-venv:
	$(PYTHON) -m venv "$(API_VENV_DIR)"
	$(API_VENV_PYTHON) -m pip install --upgrade pip

api-install: api-venv
	$(API_VENV_PIP) install -r "$(API_DEV_REQUIREMENTS)"

frontend-install:
	cd "$(FRONTEND_DIR)" && "$(NPM)" ci

pre-commit-install: api-install
	$(API_VENV_PYTHON) -m pre_commit install

pre-commit-run: api-install
	$(API_VENV_PYTHON) -m pre_commit run --all-files

# -------------------------------------------------------------------
# Backend
# -------------------------------------------------------------------

.PHONY: api-lint api-format api-format-check api-type-check api-security-lint api-test api-coverage api-integration-test api-migrate api-seed data-generate data-quality data-contracts data-scenario-report scenario-coverage-report db-backup db-restore db-readiness-evidence ml-features ml-baseline ml-trained ml-evaluate ml-metadata ml-inference ml-metrics ml-drift db-up db-down check-k6 performance-smoke

api-lint: api-install
	$(API_VENV_PYTHON) -m ruff check "$(API_DIR)/app" "$(API_DIR)/scripts" "$(API_DIR)/tests" data ml

api-format: api-install
	$(API_VENV_PYTHON) -m ruff format "$(API_DIR)/app" "$(API_DIR)/scripts" "$(API_DIR)/tests" data ml

api-format-check: api-install
	$(API_VENV_PYTHON) -m ruff format --check "$(API_DIR)/app" "$(API_DIR)/scripts" "$(API_DIR)/tests" data ml

api-type-check: api-install
	$(API_VENV_PYTHON) -m $(MYPY) --config-file "$(ROOT_DIR)/pyproject.toml"

api-security-lint: api-install ensure-reports-dir
	$(API_VENV_PYTHON) -m $(BANDIT) --exit-zero -q -r "$(API_DIR)/app" "$(API_DIR)/scripts" -f txt -o "$(ROOT_DIR)/$(API_BANDIT_REPORT)"

api-test: api-install
	cd "$(API_DIR)" && PYTHONPATH=.:$(ROOT_DIR) DATABASE_URL="$(DATABASE_URL)" .venv/bin/python -m pytest

api-coverage: api-install ensure-reports-dir
	cd "$(API_DIR)" && PYTHONPATH=.:$(ROOT_DIR) DATABASE_URL="$(DATABASE_URL)" .venv/bin/python -m pytest \
		--cov=app \
		--cov-report=term-missing \
		--cov-report=xml:"$(ROOT_DIR)/$(API_COVERAGE_XML)"

db-up:
	$(COMPOSE) up -d db

db-down:
	$(COMPOSE) down -v --remove-orphans

data-generate: api-install
	$(API_VENV_PYTHON) -m data.generator.main

data-quality: api-install ensure-reports-dir
	@rm -rf "$(DATA_OUTPUT_DIR)"
	$(API_VENV_PYTHON) -m data.generator.main --profile "$(DATA_PROFILE)" --output-dir "$(DATA_OUTPUT_DIR)"
	@$(API_VENV_PYTHON) -c "import json, pathlib, sys; report=json.loads(pathlib.Path('$(DATA_QUALITY_REPORT)').read_text()); print('Data quality status:', report.get('status')); sys.exit(0 if report.get('status') == 'passed' else 1)"
	@echo "Data quality report: $(DATA_QUALITY_REPORT)"
	@echo "Dataset manifest: $(DATA_MANIFEST_REPORT)"
	@if [ -f "$(DATA_REALISM_REPORT)" ]; then echo "Realism report: $(DATA_REALISM_REPORT)"; fi

data-contracts: api-install ensure-reports-dir
	$(API_VENV_PYTHON) scripts/data/validate_data_contracts.py --contract "$(DATA_CONTRACT)" --data-dir data/demo --event-contract "$(EVENT_CONTRACT)" --report "$(DATA_CONTRACT_REPORT)"

scenario-coverage-report: data-scenario-report

data-scenario-report: api-install ensure-reports-dir
	$(API_VENV_PYTHON) scripts/data/generate_scenario_coverage_report.py --data-dir data/demo --json-report "$(SCENARIO_COVERAGE_REPORT)" --markdown-report "$(SCENARIO_COVERAGE_MARKDOWN)"

db-backup: ensure-reports-dir
	BACKUP_DIR="$(DB_BACKUP_DIR)" DB_SERVICE="$(DB_SERVICE)" POSTGRES_USER="$(POSTGRES_USER)" POSTGRES_DB="$(POSTGRES_DB)" COMPOSE="$(COMPOSE)" scripts/db/backup.sh

db-restore: ensure-reports-dir
	@test -n "$(DB_BACKUP_FILE)" || { echo "ERROR: set DB_BACKUP_FILE=path/to/backup.dump"; exit 1; }
	DB_SERVICE="$(DB_SERVICE)" POSTGRES_USER="$(POSTGRES_USER)" POSTGRES_DB="$(POSTGRES_DB)" COMPOSE="$(COMPOSE)" scripts/db/restore.sh "$(DB_BACKUP_FILE)"

db-readiness-evidence: data-generate data-contracts data-scenario-report
	@echo "DB readiness evidence generated:"
	@echo "- $(DATA_CONTRACT_REPORT)"
	@echo "- $(SCENARIO_COVERAGE_REPORT)"
	@echo "- $(SCENARIO_COVERAGE_MARKDOWN)"

ml-features: api-install
	$(API_VENV_PYTHON) -m ml.features.demand_forecast --profile "$(ML_FEATURE_PROFILE)" --output-dir "$(ML_FEATURE_OUTPUT_DIR)"
	@echo "Feature dataset: $(ML_FEATURE_OUTPUT_DIR)/features.csv"
	@echo "Feature manifest: $(ML_FEATURE_OUTPUT_DIR)/feature_manifest.json"

ml-baseline: api-install
	$(API_VENV_PYTHON) -m ml.models.baseline_forecast --profile "$(ML_BASELINE_PROFILE)" --window-days "$(ML_BASELINE_WINDOW_DAYS)" --horizon-days "$(ML_BASELINE_HORIZON_DAYS)" --output-dir "$(ML_BASELINE_OUTPUT_DIR)"
	@echo "Baseline forecasts: $(ML_BASELINE_OUTPUT_DIR)/baseline_forecasts.csv"
	@echo "Model manifest: $(ML_BASELINE_OUTPUT_DIR)/model_manifest.json"

ml-trained: api-install
	$(API_VENV_PYTHON) -m ml.models.random_forest_forecast --profile "$(ML_TRAINED_PROFILE)" --window-days "$(ML_TRAINED_WINDOW_DAYS)" --horizon-days "$(ML_TRAINED_HORIZON_DAYS)" --holdout-days "$(ML_TRAINED_HOLDOUT_DAYS)" --n-estimators "$(ML_TRAINED_N_ESTIMATORS)" --output-dir "$(ML_TRAINED_OUTPUT_DIR)"
	@echo "Trained model artifact: $(ML_TRAINED_OUTPUT_DIR)/random_forest_model.joblib"
	@echo "Trained model metrics: $(ML_TRAINED_OUTPUT_DIR)/metrics.json"
	@echo "Trained model predictions: $(ML_TRAINED_OUTPUT_DIR)/predictions.csv"
	@echo "Trained model metadata: $(ML_TRAINED_OUTPUT_DIR)/model_metadata.json"

ml-evaluate: api-install
	$(API_VENV_PYTHON) -m ml.evaluation.baseline_report --profile "$(ML_EVALUATION_PROFILE)" --window-days "$(ML_EVALUATION_WINDOW_DAYS)" --holdout-days "$(ML_EVALUATION_HOLDOUT_DAYS)" --output-dir "$(ML_EVALUATION_OUTPUT_DIR)"
	@echo "Evaluation report: $(ML_EVALUATION_OUTPUT_DIR)/evaluation_report.json"
	@echo "Evaluation summary: $(ML_EVALUATION_OUTPUT_DIR)/evaluation_summary.md"
	@echo "Backtest predictions: $(ML_EVALUATION_OUTPUT_DIR)/backtest_predictions.csv"

ml-metadata: api-install
	$(API_VENV_PYTHON) -m ml.metadata.model_registry --profile "$(ML_METADATA_PROFILE)" --status "$(ML_METADATA_STATUS)" --output-dir "$(ML_METADATA_OUTPUT_DIR)"
	@echo "Model metadata: $(ML_METADATA_OUTPUT_DIR)/model_metadata.json"
	@echo "Model registry: $(ML_METADATA_OUTPUT_DIR)/model_registry.jsonl"

ml-inference: api-install
	$(API_VENV_PYTHON) -m ml.inference.batch_forecast --profile "$(ML_INFERENCE_PROFILE)" --window-days "$(ML_INFERENCE_WINDOW_DAYS)" --horizon-days "$(ML_INFERENCE_HORIZON_DAYS)" --holdout-days "$(ML_INFERENCE_HOLDOUT_DAYS)" --model-status "$(ML_INFERENCE_MODEL_STATUS)" --output-dir "$(ML_INFERENCE_OUTPUT_DIR)"
	@echo "Batch predictions: $(ML_INFERENCE_OUTPUT_DIR)/batch_predictions.csv"
	@echo "API forecasts: $(ML_INFERENCE_OUTPUT_DIR)/api_forecasts.csv"
	@echo "Batch manifest: $(ML_INFERENCE_OUTPUT_DIR)/batch_inference_manifest.json"

ml-metrics: api-install
	$(API_VENV_PYTHON) -m ml.observability.model_performance_metrics --profile "$(ML_METRICS_PROFILE)" --window-days "$(ML_METRICS_WINDOW_DAYS)" --horizon-days "$(ML_METRICS_HORIZON_DAYS)" --holdout-days "$(ML_METRICS_HOLDOUT_DAYS)" --model-status "$(ML_METRICS_MODEL_STATUS)" --output-dir "$(ML_METRICS_OUTPUT_DIR)"
	@echo "Model performance metrics: $(ML_METRICS_OUTPUT_DIR)/model_performance.prom"
	@echo "Model performance snapshot: $(ML_METRICS_OUTPUT_DIR)/model_performance_snapshot.json"

ml-drift: api-install
	$(API_VENV_PYTHON) -m ml.drift.demand_feature_drift --profile "$(ML_DRIFT_PROFILE)" --reference-seed "$(ML_DRIFT_REFERENCE_SEED)" --current-seed "$(ML_DRIFT_CURRENT_SEED)" --warning-threshold "$(ML_DRIFT_WARNING_THRESHOLD)" --failure-threshold "$(ML_DRIFT_FAILURE_THRESHOLD)" --output-dir "$(ML_DRIFT_OUTPUT_DIR)"
	@echo "Drift report: $(ML_DRIFT_OUTPUT_DIR)/drift_report.json"
	@echo "Drift summary: $(ML_DRIFT_OUTPUT_DIR)/drift_summary.md"

api-migrate: api-install
	cd "$(API_DIR)" && PYTHONPATH=. DATABASE_URL="$(DATABASE_URL)" .venv/bin/alembic -c alembic.ini upgrade head

api-seed: api-install
	cd "$(API_DIR)" && PYTHONPATH=. DATABASE_URL="$(DATABASE_URL)" .venv/bin/python scripts/seed_demo_data.py

api-integration-test: api-install db-up data-generate api-migrate api-seed
	cd "$(API_DIR)" && PYTHONPATH=. DATABASE_URL="$(DATABASE_URL)" REQUIRE_DB_TESTS=1 .venv/bin/python -m pytest

check-k6:
	@command -v "$(K6)" >/dev/null 2>&1 || { \
		echo "ERROR: k6 is not installed or not available in PATH."; \
		echo "Install k6 first, then rerun make performance-smoke."; \
		exit 1; \
	}

performance-smoke: check-k6 ensure-reports-dir
	@set -o pipefail; \
	API_BASE_URL="$${API_BASE_URL:-http://localhost:$(API_PORT)}" \
	$(K6) run \
		--summary-export "$(K6_API_SMOKE_SUMMARY_REPORT)" \
		"$(K6_API_SMOKE_SCRIPT)" | tee "$(K6_API_SMOKE_TEXT_REPORT)"
	@echo "k6 text report: $(K6_API_SMOKE_TEXT_REPORT)"
	@echo "k6 summary report: $(K6_API_SMOKE_SUMMARY_REPORT)"

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

ci-local: compose-config data-quality data-contracts data-scenario-report api-lint api-format-check api-type-check api-security-lint api-coverage frontend-test frontend-lint frontend-build
	@echo "Local CI preflight passed."

# -------------------------------------------------------------------
# Terraform / Infrastructure as Code
# These targets are local-first helpers. They validate and collect evidence
# before Terraform is promoted to GitHub Actions or Jenkins automation.
# top-level commands --> iac-scan, terraform-plan-dev
# -------------------------------------------------------------------

.PHONY: check-terraform check-tflint check-checkov check-tflint-config check-checkov-config ensure-iac-reports-dir terraform-fmt terraform-fmt-check terraform-init-local terraform-validate terraform-plan-dev tflint-init tflint-report iac-critical-guardrails iac-secret-scan checkov-report checkov-json checkov-scan iac-scan

check-terraform:
	@command -v "$(TERRAFORM)" >/dev/null 2>&1 || { \
		echo "ERROR: terraform is not installed or not available in PATH."; \
		exit 1; \
	}

check-tflint:
	@command -v "$(TFLINT)" >/dev/null 2>&1 || { \
		echo "ERROR: tflint is not installed or not available in PATH."; \
		exit 1; \
	}

check-checkov:
	@command -v "$(CHECKOV)" >/dev/null 2>&1 || { \
		echo "ERROR: checkov is not installed or not available in PATH."; \
		exit 1; \
	}

check-tflint-config:
	@test -f "$(TFLINT_CONFIG)" || { \
		echo "ERROR: TFLint config not found: $(TFLINT_CONFIG)"; \
		exit 1; \
	}

check-checkov-config:
	@test -f "$(CHECKOV_CONFIG)" || { \
		echo "ERROR: Checkov config not found: $(CHECKOV_CONFIG)"; \
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

tflint-init: check-tflint check-tflint-config
	$(TFLINT) --init --config "$(TFLINT_CONFIG)"

tflint-report: tflint-init ensure-iac-reports-dir
	@set -o pipefail; \
	cd "$(ROOT_DIR)/$(INFRA_DIR)" && \
	$(TFLINT) --recursive \
		--config "$(TFLINT_CONFIG)" \
		--format compact | tee "$(ROOT_DIR)/$(TFLINT_REPORT)"

iac-critical-guardrails: ensure-iac-reports-dir
	@echo "[iac-critical-guardrails] Checking for IAM users, access keys, AdministratorAccess and wildcard IAM actions..."
	@if grep -R -I --include="*.tf" --exclude-dir=".terraform" \
		-E 'aws_iam_access_key|aws_iam_user|policy_arn[[:space:]]*=[[:space:]]*"arn:aws:iam::aws:policy/AdministratorAccess"|actions[[:space:]]*=[[:space:]]*\[[^]]*"\*"' \
		"$(INFRA_DIR)"; then \
		echo "ERROR: Critical IaC guardrail violation found. Review IAM definitions before merging."; \
		exit 1; \
	else \
		echo "[iac-critical-guardrails] Critical IaC guardrail checks passed."; \
	fi

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

checkov-report: check-checkov check-checkov-config ensure-iac-reports-dir
	@set -o pipefail; \
	$(CHECKOV) \
		--config-file "$(CHECKOV_CONFIG)" \
		--directory "$(INFRA_DIR)" \
		--framework terraform \
		--soft-fail \
		--output cli | tee "$(CHECKOV_REPORT)"

checkov-json: check-checkov check-checkov-config ensure-iac-reports-dir
	$(CHECKOV) \
		--config-file "$(CHECKOV_CONFIG)" \
		--directory "$(INFRA_DIR)" \
		--framework terraform \
		--soft-fail \
		--output json > "$(CHECKOV_JSON_REPORT)"

checkov-scan: checkov-report checkov-json
	@echo "Checkov report-only scan completed. Reports saved under $(IAC_REPORTS_DIR)."

iac-scan: terraform-fmt-check terraform-validate iac-critical-guardrails iac-secret-scan tflint-report checkov-scan
	@echo "IaC scan passed. Reports saved under $(IAC_REPORTS_DIR). Use 'make terraform-plan-dev' separately when AWS credentials are available."

# -------------------------------------------------------------------
# Docker / Compose
# -------------------------------------------------------------------

.PHONY: docker-build compose-config compose-up compose-down compose-logs compose-smoke streaming-smoke observability-smoke observability-demo-traffic compose-rebuild-smoke compose-ci broker-up broker-topics realtime-consumer observability-up k8s-smoke

docker-build:
	docker build -t "$(API_IMAGE)" "$(API_DIR)"
	docker build -t "$(FRONTEND_IMAGE)" "$(FRONTEND_DIR)"

compose-config:
	$(COMPOSE) config

compose-up:
	$(COMPOSE) up --build -d

broker-up:
	$(COMPOSE) up -d redpanda redpanda-init

broker-topics:
	$(COMPOSE) exec redpanda rpk topic list --brokers redpanda:9092

realtime-consumer:
	cd "$(API_DIR)" && PYTHONPATH=. DATABASE_URL="$(DATABASE_URL)" RETAILOPS_BROKER_BOOTSTRAP_SERVERS="$(RETAILOPS_BROKER_BOOTSTRAP_SERVERS)" .venv/bin/python scripts/run_realtime_consumer.py

observability-up:
	$(COMPOSE) up --build -d db migrate seed api prometheus grafana

compose-down:
	$(COMPOSE) down -v --remove-orphans

compose-logs:
	$(COMPOSE) logs --no-color

compose-smoke:
	chmod +x "$(SMOKE_SCRIPT)"
	API_BASE_URL="http://localhost:$(API_PORT)" FRONTEND_BASE_URL="http://localhost:$(FRONTEND_PORT)" "$(SMOKE_SCRIPT)"

streaming-smoke:
	chmod +x "$(STREAMING_SMOKE_SCRIPT)"
	API_BASE_URL="http://localhost:$(API_PORT)" PROMETHEUS_BASE_URL="http://localhost:$(PROMETHEUS_PORT)" COMPOSE="$(COMPOSE)" "$(STREAMING_SMOKE_SCRIPT)"

observability-smoke: ensure-reports-dir
	chmod +x "$(OBSERVABILITY_SMOKE_SCRIPT)"
	API_BASE_URL="http://localhost:$(API_PORT)" PROMETHEUS_BASE_URL="http://localhost:$(PROMETHEUS_PORT)" GRAFANA_BASE_URL="http://localhost:$(GRAFANA_PORT)" OBSERVABILITY_REPORTS_DIR="$(OBSERVABILITY_REPORTS_DIR)" "$(OBSERVABILITY_SMOKE_SCRIPT)"

observability-demo-traffic: ensure-reports-dir
	chmod +x "$(OBSERVABILITY_DEMO_TRAFFIC_SCRIPT)"
	API_BASE_URL="http://localhost:$(API_PORT)" PROMETHEUS_BASE_URL="http://localhost:$(PROMETHEUS_PORT)" GRAFANA_BASE_URL="http://localhost:$(GRAFANA_PORT)" COMPOSE="$(COMPOSE)" OBSERVABILITY_REPORTS_DIR="$(OBSERVABILITY_REPORTS_DIR)" "$(OBSERVABILITY_DEMO_TRAFFIC_SCRIPT)"

k8s-smoke: ensure-reports-dir
	chmod +x "$(KUBERNETES_SMOKE_SCRIPT)"
	K8S_REPORTS_DIR="$(REPORTS_DIR)/k8s" "$(KUBERNETES_SMOKE_SCRIPT)"

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
	if [[ $$status -eq 0 ]]; then \
		echo "[compose-ci] Running streaming smoke tests..."; \
		chmod +x "$(STREAMING_SMOKE_SCRIPT)"; \
		API_BASE_URL="http://localhost:$(API_PORT)" PROMETHEUS_BASE_URL="http://localhost:$(PROMETHEUS_PORT)" COMPOSE="$(COMPOSE)" "$(STREAMING_SMOKE_SCRIPT)" || status=$$?; \
	fi; \
	if [[ $$status -eq 0 ]]; then \
		echo "[compose-ci] Running observability smoke tests..."; \
		chmod +x "$(OBSERVABILITY_SMOKE_SCRIPT)"; \
		API_BASE_URL="http://localhost:$(API_PORT)" PROMETHEUS_BASE_URL="http://localhost:$(PROMETHEUS_PORT)" GRAFANA_BASE_URL="http://localhost:$(GRAFANA_PORT)" OBSERVABILITY_REPORTS_DIR="$(OBSERVABILITY_REPORTS_DIR)" "$(OBSERVABILITY_SMOKE_SCRIPT)" || status=$$?; \
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

# -------------------------------------------------------------------
# repo-structure
# -------------------------------------------------------------------

.PHONY: docs-repo-structure

docs-repo-structure:
	@{ \
		echo "# RetailOps repository structure snapshot"; \
		echo "#"; \
		echo "# Generated: $$(date -u +%Y-%m-%dT%H:%M:%SZ)"; \
		echo "# Purpose: Static repository tree snapshot for documentation/release evidence."; \
		echo "# Refresh command:"; \
		echo '#   make docs-repo-structure'; \
		echo "#"; \
		echo "# Note:"; \
		echo "# This file is intentionally static and can become stale in active development."; \
		echo "# Refresh it during release evidence updates or before publishing portfolio documentation."; \
		echo ""; \
		echo 'tree -a -I "node_modules|dist|build|coverage|__pycache__|*.pyc|.pytest_cache|.mypy_cache|.ruff_cache|.git|.DS_Store|.venv|venv|env|.env|.env.local"'; \
		tree -a -I "node_modules|dist|build|coverage|__pycache__|*.pyc|.pytest_cache|.mypy_cache|.ruff_cache|.git|.DS_Store|.venv|venv|env|.env|.env.local"; \
	} > docs/repo-structure.txt
