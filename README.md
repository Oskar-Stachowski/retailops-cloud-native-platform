# Cloud-Native RetailOps Platform

## Overview

Cloud-Native RetailOps Platform is a DevOps case study project focused on building a production-oriented retail operations platform with a documented path toward cloud deployment, Kubernetes, and future MLOps capabilities.

The platform is designed to improve operational visibility, support sales and inventory decisions, detect business anomalies, and provide a scalable foundation for future AI-driven retail optimization.

The project demonstrates how modern DevOps, cloud-native architecture, Infrastructure as Code, CI/CD, observability, and security practices can be combined into one end-to-end platform. MLOps and Kubernetes are documented as future platform extensions unless marked otherwise in the status matrix below.

<p align="center">
  <img src="GPTimages/Architecture.png" width="90%"/>
</p>

---

## Implementation Status

This repository intentionally separates implemented components from target architecture. The table below is the source of truth for what exists today.

| Area | Current status | Evidence |
|---|---|---|
| Local application runtime | Implemented | `docker-compose.yml`, `Makefile`, `scripts/ci/compose_smoke.sh` |
| Backend API | Implemented | `services/api/`, Alembic migrations, API tests |
| Frontend operator UI | Implemented | `frontend/src/`, Nginx runtime image, frontend CI |
| PostgreSQL demo data | Implemented | `data/demo/`, `data/generator/`, seed scripts |
| CI/CD quality gates | Implemented | `.github/workflows/`, `Jenkinsfile`, root `Makefile` |
| Terraform AWS foundation | Implemented foundation only | `infra/environments/dev`, reusable Terraform modules |
| Observability | Implemented for local stack | Prometheus, Grafana provisioning, metrics endpoint, smoke tests |
| Security automation | Implemented for scanning and IaC guardrails | Gitleaks, Trivy, pip-audit, npm audit, TFLint, Checkov |
| Event streaming | Partially implemented | Redpanda topics, event contracts, replay data, live metrics read model, local K8s broker and consumer deployment; producer/replay E2E is future work |
| Cloud workload deployment | Designed only | AWS architecture docs and Terraform foundation; no permanent app runtime is deployed |
| Kubernetes/EKS | Base manifests started | `k8s/base/`, `k8s/overlays/dev`, `scripts/ci/kubernetes_smoke.sh`; namespace, API/frontend services, local dev PostgreSQL, Redpanda, realtime consumer, migration and seed jobs with probes/resources and local nginx ingress |
| MLOps/model lifecycle | Designed only | `ml/README.md` and architecture docs; no training/inference pipeline is implemented yet |

---

## Business Context

Retail and e-commerce organizations often face problems such as:

- Inaccurate demand forecasting
- Stockouts and overstocks
- Delayed reaction to business events
- Fragmented operational visibility
- Manual deployment and infrastructure processes
- Weak production-readiness for ML use cases

This project shows how a cloud-native platform can address these problems by connecting business data, applications, automation, analytics, and operational controls.

---

## Project Goals

The main goals of the project are to:

- Build a realistic DevOps portfolio project based on a business case
- Design a production-oriented AWS cloud architecture
- Containerize application services
- Automate build, test, scan, and deployment workflows
- Provision foundational AWS infrastructure using Terraform
- Implement observability and security controls
- Document future Kubernetes and MLOps capabilities without presenting them as current runtime features

---

## Key Capabilities

The platform is designed around the following capabilities:

- Retail operations dashboard
- Product, sales, inventory, and order intelligence
- Demand forecasting foundation
- Anomaly detection concept
- Event-driven processing design
- CI/CD automation
- Infrastructure as Code
- Observability with metrics, logs, dashboards, and alerts
- DevSecOps controls for code, containers, dependencies, and infrastructure
- Future Kubernetes deployment and MLOps model lifecycle design

---

## Technology Stack

### Application

- Python
- FastAPI
- REST API
- PostgreSQL
- Docker
- Docker Compose

### Implemented DevOps & Cloud

- AWS
- Terraform
- Jenkins
- GitHub
- GitHub Actions
- Amazon ECR

### Implemented Observability

- Prometheus
- Grafana
- AWS CloudWatch

### Implemented Security / DevSecOps

- Trivy
- Gitleaks
- pip-audit
- npm audit
- TFLint
- Checkov
- AWS IAM

### Designed / Future Platform Areas

- Kubernetes / EKS deployment
- ML lifecycle design
- Model versioning concept
- Drift monitoring concept
- Retraining workflow concept
- AWS Secrets Manager or SSM Parameter Store for cloud runtime secrets
- Runtime threat detection
- Centralized log platform such as OpenSearch or Loki

---

## Architecture

The platform follows a layered cloud-native architecture:

1. Business & User Layer
2. Application & API Layer
3. Data & Event Processing Layer
4. ML / Intelligence Layer
5. Platform & Infrastructure Layer
6. Security, Observability & Governance Layer

<p align="center">
  <img src="GPTimages/Architecture-Layers.png" width="90%"/>
</p>

More details are available in:

- [Case Study](case-study.md)
- [Architecture Diagrams](docs/diagrams/01-system-context-and-outcomes.md)
- [AWS Architecture](docs/aws-architecture.md)
- [CI/CD Pipeline](ci-cd/README.md)
- [Security & Governance](security/README.md)
- [Observability](observability/README.md)

---

## Repository Structure

This repository is organized as a production-style cloud-native platform monorepo.

## Top-Level Folders

### `docs/`
Contains architecture, business case, technical documentation and diagrams.

### `services/`
Contains backend microservices responsible for platform business capabilities.

### `frontend/`
Contains the user-facing web application.

### `ml/`
Contains the future MLOps scope and model lifecycle assumptions. Training, inference, experiments and model lifecycle components are not implemented yet.

### `data/`
Contains data schemas and samples.

### `infra/`
Contains Infrastructure as Code definitions, mainly Terraform modules and environment configurations.

### `k8s/`
Contains the Kubernetes runtime scope. The current base includes namespace, shared configuration, API/frontend service manifests and local nginx ingress, plus a dev overlay for local PostgreSQL, Redpanda, realtime consumer, migrations and seed data; Helm charts are not implemented yet.

### `observability/`
Contains monitoring, logging, dashboard and alerting configuration.

### `security/`
Contains DevSecOps tools, scanning configuration and policy definitions.

### `ci-cd/`
Contains CI/CD pipeline definitions for application, infrastructure and security workflows.

### `tests/`
Contains automated tests.

### `scripts/`
Contains helper scripts for local development, testing and deployment.

---

## 🚀 Local Development

Run the full RetailOps local platform using Docker Compose.

### 🧱 Architecture

The local environment runs a minimal full-stack setup:

```text
Frontend → API → PostgreSQL
          ↘ Redpanda event broker
```

* Frontend: Nginx-served React operator UI
* API: FastAPI service
* Database: PostgreSQL
* Event broker: Redpanda, Kafka-compatible local broker for event topic validation

---

### 📦 Prerequisites

Install the following tools:

* Docker
* Docker Compose
* Git

> Python and Make are **not required** for running the app via Docker Compose.

---

### 📥 Clone the repository

```bash
git clone https://github.com/your-username/cloud-native-retailops-platform.git
cd cloud-native-retailops-platform
```

---

### ⚙️ Configure environment variables

```bash
cp .env.example .env
```

You can optionally adjust ports and database credentials in `.env`.

---

### ▶️ Run the full stack

```bash
docker compose up --build
```

### Docker Compose Local Runtime

The local Docker Compose runtime starts the full RetailOps stack:

```text
PostgreSQL -> migrations -> demo seed -> FastAPI API -> Nginx-served React frontend
Redpanda -> local real-time event topics
```

Run the stack in the background:

```bash
docker compose up --build -d
```

Verify the full runtime:

```bash
make compose-ci
```

The Compose CI flow checks API health, database readiness, selected DB-backed
endpoints, the frontend root page, the frontend `/api` proxy, Redpanda topic
initialization, `/dashboard/live-operations`, `/metrics`, Prometheus target
health and stream alert rules.

For a faster check against an already running stack:

```bash
./scripts/ci/compose_smoke.sh
make streaming-smoke
```

Useful URLs:

* Frontend: http://localhost:3000
* API: http://localhost:8000
* API health: http://localhost:8000/health
* Frontend API proxy: http://localhost:3000/api/health
* Redpanda Kafka API: localhost:19092
* Redpanda Admin API: http://localhost:19644

Start only the local event broker and create topics:

```bash
make broker-up
```

List local event topics:

```bash
make broker-topics
```

Run the long-running local realtime consumer against the host-exposed broker:

```bash
make realtime-consumer
```

Stop the stack:

```bash
docker compose down
```

---

### 🌐 Access the services

* Frontend: http://localhost:3000
* API: http://localhost:8000
* Health check: http://localhost:8000/health

---

### 🩺 Health check (CLI)

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{
  "status": "ok",
  "service": "retailops-api",
  "environment": "local"
}
```

---

### 🛑 Stop the stack

```bash
docker compose down
```

---

### 🧪 Useful commands

Check running containers:

```bash
docker compose ps
```

View logs:

```bash
docker compose logs -f
```

---

### 📌 Notes

* This is a **local-first platform environment** designed to validate application, data, observability, and delivery behavior without running permanent cloud workloads.
* AWS Terraform foundation and CI/CD automation are implemented; Kubernetes workload deployment remains future scope beyond the initial API/frontend, dev database/broker, realtime consumer and one-shot job manifests.
* The frontend is an operator dashboard for the local platform, not a public production service.


## CI/CD Pipeline

The current delivery workflow automates validation and evidence generation:

1. Code commit
2. Pull request review
3. Formatting and linting
4. Unit tests
5. Static code analysis
6. Dependency scanning
7. Container image build
8. Container image scanning
9. Docker Compose smoke checks
10. Terraform validation and IaC scanning
11. Security evidence upload

Container registry publishing and workload deployment are future promotion steps, not part of the default CI path.

Evidence entry points:

- Curated reviewer evidence: `docs/evidence/index.md`
- Raw report policy and snapshots: `ci-cd/reports/README.md`

<p align="center">
  <img src="GPTimages/CI-CD-Pipeline-Delivery-Workflow.png" width="90%"/>
</p>

---

## Infrastructure as Code

Terraform is used to define the AWS foundation in a repeatable way.

The implemented foundation includes:

- Networking
- IAM
- Container registry
- AWS Budget guardrail
- CloudWatch log groups
- Security and governance tags

The foundation intentionally does not create permanent compute workloads, EKS, RDS, load balancers, or object storage yet. Terraform code is organized by environment and reusable modules.

---

## Kubernetes Deployment

Kubernetes is a target runtime design. The repository now includes base manifests for namespace, shared runtime configuration, API service, frontend service, local dev PostgreSQL, Redpanda, realtime consumer, migrations and seed data, not a complete deployment path.

The future Kubernetes scope is designed to support:

- Backend APIs
- Frontend services
- Workers
- Scheduled jobs
- ML inference services
- Event consumers
- Autoscaling
- Rolling deployments
- Health checks
- Workload isolation

---

## Observability

The implemented observability layer provides local API metrics, Prometheus scraping, Grafana dashboards, alert rules, and smoke checks.

Current and future observability capabilities include:

- Application metrics
- Infrastructure metrics
- Dashboards
- Alerting
- Service health checks
- Stream processing metrics
- Future centralized logs, deployment monitoring, data pipeline monitoring, and model performance monitoring

---

## Security

Security automation is integrated into the platform and delivery workflow.

The project currently includes:

- Least-privilege IAM design
- Dependency scanning
- Container image scanning
- Secret scanning
- IaC linting and policy scanning
- Network segmentation
- Auditability of infrastructure and deployment changes

Cloud runtime secret management and runtime threat detection are future hardening items.

---

## Project Roadmap

### Phase 1 — Foundation

- Basic backend API
- Health endpoint
- Dockerized local environment
- Initial database model
- Basic CI pipeline
- Initial documentation

### Phase 2 — Production-Ready Platform

- Terraform infrastructure
- Kubernetes deployment design
- CI/CD pipeline
- Container registry workflow
- Observability foundation
- Security scanning

### Phase 3 — Real-Time Operations

- Event-driven processing
- Async workers
- Business event ingestion
- Operational alerts
- Improved monitoring

### Phase 4 — MLOps Foundation

- Forecasting model lifecycle
- Model versioning
- Model monitoring
- Retraining workflow
- Drift detection concept

### Phase 5 — Enterprise Optimization

- Advanced recommendations
- Scenario simulation
- Multi-environment platform
- FinOps controls
- Advanced governance

---

## Documentation

The project documentation is split into several files and directories:

- `case-study.md` — business and executive-level case study
- `docs/diagrams/` — architecture and maturity diagrams
- `docs/aws-architecture.md` — AWS design and service rationale
- `ci-cd/README.md` — CI/CD pipeline and delivery workflow
- `security/README.md` — DevSecOps and governance controls
- `observability/README.md` — monitoring, metrics and alerting
- `docs/real-time-event-contracts.md` — real-time event model
- `docs/local-event-broker.md` — local Redpanda broker, consumer runner and streaming smoke checks
- `docs/runbooks/local-kubernetes-runbook.md` — local Kubernetes validation and run procedure
- `docs/live-metrics-persistence.md` — persisted live operations read model

---

## Project Status

Current status: **Implemented local platform with documented future extensions**

This repository is being developed as a portfolio-grade DevOps project. Implemented components and target architecture are separated in the implementation status matrix so reviewers can distinguish working platform capabilities from future design scope.

---

## Why This Project Matters

This project demonstrates practical skills across the full DevOps lifecycle:

- Application development
- Containerization
- CI/CD
- AWS foundation design
- Infrastructure as Code
- Kubernetes target design
- Observability
- Security automation
- Documented MLOps roadmap
- Production-readiness thinking

It is designed to show not only technical knowledge, but also the ability to connect engineering decisions with business outcomes such as faster delivery, lower operational risk, better scalability, and improved decision-making.

---

## Author

**Oskar Stachowski**

> DevOps Engineer focused on AWS, Terraform and cloud-native delivery

> Building production-oriented platform systems

> CI/CD, observability and security automation

---

## Notes

Parts of the documentation and visual materials were supported with AI tools, including ChatGPT.

Architecture decisions, implementation choices, technical validation, and final project structure were reviewed and adapted independently by the author.

---

## License

This project is licensed under the MIT License.
