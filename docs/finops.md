# RetailOps FinOps Strategy

## 1. Purpose of this document

This document defines the early-stage FinOps strategy for the RetailOps Platform.

The goal is to keep the MVP cost-aware by using a **local-first development model** and **synthetic or seed retail data** before introducing always-on AWS infrastructure. The platform still has a production-oriented AWS target architecture, but the early delivery path should avoid unnecessary cloud spending until there is enough implementation maturity and business value evidence to justify it.

This document explains:

- which parts of the platform should run locally during MVP,
- which data should be synthetic or seeded,
- which AWS services belong to target architecture rather than immediate MVP runtime,
- how cloud costs should be controlled when AWS resources are introduced,
- what evidence proves that the project is cost-aware.

---

## 2. FinOps principle for RetailOps

The project follows one main FinOps principle:

> **Build and prove the MVP locally first, then introduce AWS services gradually when they are justified by business value, production-readiness needs, or portfolio evidence.**

This is important because RetailOps is a portfolio-grade DevOps / MLOps case study, not a real production platform with real users and production traffic. Running enterprise AWS services too early would increase cost without proving additional business value.

The project should therefore clearly separate:

| Scope type | Meaning | Example |
|---|---|---|
| **Implemented MVP** | Components that can run locally and produce evidence now. | FastAPI service, Docker Compose, PostgreSQL, sample data, `/health` endpoint. |
| **Designed target architecture** | Components documented as the intended production direction. | EKS, RDS, ECR, CloudWatch, Terraform-managed AWS foundation. |
| **Future maturity scope** | Advanced capabilities introduced after MVP or production-readiness foundation. | Event-driven processing, full MLOps automation, drift monitoring, multi-environment AWS deployment. |

---

## 3. Why local-first matters

A local-first MVP reduces early AWS cost and improves delivery speed.

### 3.1. Business reasons

Local-first development supports the business case because it allows the project to validate the platform idea before paying for cloud infrastructure.

The MVP should first prove that RetailOps can support decisions such as:

- which products have stockout or overstock risk,
- which alerts require operational action,
- which anomalies should be investigated,
- whether a simple forecast or risk signal can support inventory decisions,
- whether the platform can connect business signals with workflow status and evidence.

These questions do not require EKS, RDS, or always-on cloud observability during the first phase.

### 3.2. Technical reasons

Local-first development also improves technical execution:

- developers can run the platform without cloud credentials,
- CI can validate basic behavior without provisioning infrastructure,
- demo scenarios can be reproduced reliably,
- synthetic data can be reset and regenerated easily,
- failures are cheaper and faster to debug,
- the project avoids accidental cloud spend while still keeping cloud-ready structure.

### 3.3. Portfolio reasons

For a DevOps portfolio project, local-first strategy shows mature engineering thinking. It communicates that the project author understands the difference between:

- designing an enterprise target architecture,
- implementing a realistic MVP,
- controlling cloud cost,
- avoiding overengineering.

This is more credible than deploying every advanced AWS component immediately without a clear reason.

---

## 4. MVP local-first runtime

The MVP should be runnable with local tooling first.

### 4.1. Recommended MVP runtime components

| Component | MVP mode | Purpose | Cost impact |
|---|---|---|---|
| Backend API | Local FastAPI container | Expose health, product, inventory, alert, and dashboard endpoints. | No AWS cost. |
| Frontend | Local development server or container | Show dashboard/product view when implemented. | No AWS cost. |
| Database | Local PostgreSQL container or local seed files | Store sample products, sales, stock, prices, and alerts. | No AWS cost. |
| Data loading | Seed scripts / CSV / JSON | Reproducible demo data for business workflows. | No AWS cost. |
| ML baseline | Local script / notebook / simple service | Generate baseline forecast or anomaly examples. | No AWS cost. |
| CI validation | GitHub Actions or local checks | Run tests, linting, Docker build, and scans. | No AWS infrastructure cost. |
| Observability | Logs, health endpoint, optional local Prometheus/Grafana | Validate basic service health and visibility. | No AWS cost if local. |
| Security scans | Local or CI Trivy/Snyk/Sonar checks | Validate image/dependency/code quality. | No AWS runtime cost. |

### 4.2. MVP local evidence

The local MVP should produce evidence such as:

- successful `docker compose up --build`,
- successful `/health` response,
- seeded retail data loaded into the app or database,
- example `/inventory-risk` or `/alerts` response,
- test report for basic business logic,
- CI run with build/test/scan result,
- local logs showing application startup and request handling,
- screenshot of local dashboard when frontend is available.

---

## 5. Synthetic-data strategy

The project should use synthetic or seed data during MVP.

### 5.1. Why synthetic data is appropriate

Synthetic data is appropriate because the project does not depend on a real retail client, real production systems, or sensitive business data.

Synthetic data helps the project:

- avoid privacy and licensing issues,
- create controlled business scenarios,
- test edge cases such as missing stock, demand spikes, stale data, negative values, or unusual price changes,
- make demo scenarios reproducible,
- support CI tests without external dependencies,
- explain business workflows clearly.

### 5.2. Data domains required for MVP

The MVP seed dataset should represent the minimum retail reality required by the case study.

| Data domain | Example fields | Why it is needed |
|---|---|---|
| Products | `sku`, `product_name`, `category`, `brand`, `status` | Enables Product 360, category views, and product-level decisions. |
| Sales | `sku`, `date`, `sales_qty`, `sales_value`, `channel` | Supports sales trends, demand signals, and anomaly examples. |
| Inventory | `sku`, `stock_qty`, `warehouse`, `last_updated_at` | Supports stockout and overstock risk. |
| Pricing | `sku`, `price`, `currency`, `valid_from`, `valid_to` | Supports pricing context and commercial review. |
| Promotions | `campaign_id`, `sku`, `start_date`, `end_date`, `expected_lift` | Supports campaign-driven demand interpretation. |
| Alerts | `alert_id`, `sku`, `alert_type`, `severity`, `status`, `created_at` | Supports operations triage and workflow completion. |
| Forecasts | `sku`, `forecast_date`, `forecast_qty`, `model_version` | Supports inventory planning and ML readiness. |
| Workflow actions | `action_id`, `alert_id`, `actor_role`, `action`, `reason`, `created_at` | Supports auditability and decision traceability. |

### 5.3. Required demo scenarios

The synthetic data should include controlled scenarios, not only random rows.

Recommended MVP scenarios:

| Scenario | Description | Related workflow |
|---|---|---|
| Stockout risk | A product has high recent sales and low stock. | Inventory review, operations triage. |
| Overstock risk | A product has high stock and weak sales. | Inventory review, finance review. |
| Sales spike | Sales increase unusually after campaign or external event. | Anomaly investigation, commercial review. |
| Sales drop | Sales fall despite available stock. | Anomaly investigation. |
| Pricing anomaly | Price changes unexpectedly or differs from normal range. | Commercial review. |
| Stale inventory data | Inventory timestamp is older than expected. | Operations triage, data quality. |
| Missing forecast | Forecast is unavailable for selected product. | Inventory review, ML readiness. |
| False positive alert | Alert is dismissed with reason. | Workflow feedback, anomaly tuning. |

### 5.4. Synthetic data rules

Synthetic data should follow these rules:

1. **Business-realistic enough** — values should resemble retail operations, even if simplified.
2. **Deterministic where useful** — demo scenarios should be reproducible.
3. **Edge-case friendly** — include missing values, stale timestamps, low stock, demand spikes, and invalid examples for tests.
4. **Clearly labeled** — documentation should state that the data is synthetic.
5. **Safe by default** — no real customer data, no personal data, no confidential supplier data.
6. **Connected to tests** — seed data should support unit, API, and data-quality tests.

---

## 6. AWS scope boundary

AWS remains important for the target architecture, but not every AWS component should run from day one.

### 6.1. Local MVP vs target AWS architecture

| Capability | MVP mode | Target AWS mode | Reason to defer AWS |
|---|---|---|---|
| API runtime | Docker Compose | EKS or ECS/EKS-based deployment | Local API proves business and technical flow without cluster cost. |
| Database | Local PostgreSQL | Amazon RDS | Managed database cost is not needed before real cloud environment. |
| Object storage | Local files / sample data folder | Amazon S3 | MVP can use local seed files before data lake/storage design is required. |
| Container registry | Local image build | Amazon ECR | ECR becomes useful when cloud deployment starts. |
| Kubernetes | Not required for first local MVP | Amazon EKS | EKS is valuable for production-readiness, but expensive/complex for initial proof. |
| Infrastructure provisioning | Documented Terraform structure | Terraform-managed AWS resources | Terraform can be designed before applying paid resources. |
| Observability | Logs, `/health`, optional local Prometheus/Grafana | CloudWatch, Prometheus/Grafana, OpenSearch | Cloud observability is justified after cloud runtime exists. |
| Event processing | Batch/seed scripts | EventBridge, MSK, SQS/SNS, or equivalent | Event-driven architecture belongs to later maturity. |
| Secrets | `.env.example`, local env variables | AWS Secrets Manager / Parameter Store | Managed secrets are needed for cloud environments, not basic local demo. |
| ML lifecycle | Local scripts/reports | Managed or self-hosted MLOps components | Full MLOps should follow baseline model evidence. |

### 6.2. Deferred AWS services

The following services should be treated as target or later-phase services unless a specific task requires them:

- Amazon EKS,
- Amazon RDS,
- Amazon MSK or other managed streaming service,
- OpenSearch Service,
- long-retention CloudWatch logs,
- multi-environment VPC architecture,
- managed ML training/inference services,
- always-on monitoring stacks,
- NAT Gateway for non-essential demo environments,
- multi-region deployment components.

The purpose is not to avoid AWS permanently. The purpose is to introduce AWS gradually and intentionally.

---

## 7. Cloud cost controls when AWS is introduced

When AWS resources are introduced, the project should follow basic cost-control rules.

### 7.1. Environment policy

| Environment | Purpose | Cost rule |
|---|---|---|
| Local | Development and MVP demo | Default environment; no AWS runtime required. |
| Dev AWS | Short-lived cloud validation | Create only when needed; destroy after validation. |
| Staging AWS | Production-like testing | Introduce only after MVP is stable. |
| Production-like AWS | Target architecture demonstration | Optional portfolio milestone, not early MVP requirement. |

### 7.2. Shutdown and cleanup discipline

The project should document and follow cleanup rules:

- destroy temporary Terraform environments after experiments,
- stop or remove unused compute resources,
- avoid unnecessary always-on clusters,
- avoid long log retention in demo environments,
- avoid NAT Gateway unless justified,
- keep only required container images in registries,
- tag resources consistently when AWS is used,
- review cost after every cloud experiment.

### 7.3. Cost tags

When AWS resources are created, they should use standard tags.

Recommended tags:

| Tag | Example value | Purpose |
|---|---|---|
| `Project` | `RetailOps` | Identifies project cost. |
| `Environment` | `dev`, `staging`, `prod-like` | Separates environment cost. |
| `Owner` | `oskar` | Identifies responsible owner. |
| `ManagedBy` | `terraform` | Indicates provisioning method. |
| `CostCenter` | `portfolio` | Supports cost grouping. |
| `Lifecycle` | `temporary`, `persistent` | Helps identify cleanup candidates. |

---

## 8. FinOps indicators

The Enterprise Scorecard defines two key FinOps indicators for this project.

### 8.1. Estimated Monthly Cloud Cost

- **Type:** FinOps KPI
- **Decision supported:** Is the target architecture financially reasonable for the current maturity stage?
- **How to measure:** Estimate monthly cost for planned AWS services and environments.
- **Suggested formula:** Sum of estimated monthly costs per service or component.
- **MVP evidence:** Cost estimate document, AWS Pricing Calculator export, architecture cost assumptions.
- **Suggested target:** MVP should remain cost-aware and avoid unnecessary always-on enterprise services.
- **Measurement level:** Target maturity / Estimated.

### 8.2. Idle Baseline Monthly Cloud Cost

- **Type:** FinOps KPI / Cost Risk Indicator
- **Decision supported:** What is the estimated monthly cloud cost of running RetailOps when there is no user traffic or business activity?
- **How to measure:** Estimate the cost of always-on cloud resources required to keep the platform available, even when nobody is using it.
- **Suggested formula:** `Idle Baseline Monthly Cloud Cost = sum of estimated monthly costs of always-on resources`
- **MVP evidence:** AWS Pricing Calculator estimate, Terraform resource list, architecture cost assumptions, and a short note explaining which components are always-on.
- **Suggested target:** MVP should minimize idle cost by using local-first development, small environments, scheduled shutdowns, serverless options where appropriate, and avoiding unnecessary always-on enterprise services.
- **Measurement level:** Mostly producer-owned / Estimated / MVP + Target maturity.

---

## 10. Relationship to architecture and delivery

This FinOps strategy affects several project areas.

### 10.1. Architecture

The architecture can still show AWS, Kubernetes, observability, and MLOps as target capabilities, but documentation should clearly state that the first MVP is local-first.

This avoids misleading readers into thinking that all enterprise components are already deployed.

### 10.2. CI/CD

Early CI/CD should validate local behavior first:

- formatting,
- linting,
- unit tests,
- API tests,
- Docker build,
- dependency and image scans,
- local smoke test.

Cloud deployment stages can be added later after the local MVP is stable.

### 10.3. Testing

Synthetic data should become part of the test strategy. Tests should validate:

- data completeness,
- stock risk classification,
- alert generation,
- API response shape,
- workflow status transitions,
- handling of stale or missing data.

### 10.4. Security

Synthetic data reduces early data protection risk. Local-first does not remove the need for security hygiene, but it reduces exposure while the project is still immature.

Security expectations still include:

- no secrets committed to Git,
- `.env.example` instead of real credentials,
- dependency scanning,
- container image scanning,
- clear separation between local mock data and future production data.

### 10.5. Observability

The MVP should start with simple observability:

- `/health` endpoint,
- logs,
- test output,
- CI evidence,
- optional local metrics.

Cloud observability should be introduced when workloads actually run in AWS.
