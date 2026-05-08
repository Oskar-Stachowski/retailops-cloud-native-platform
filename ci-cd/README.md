# CI/CD

This directory contains the CI/CD design, pipeline assets, local release-confidence commands, security gates, and delivery evidence conventions for the RetailOps Cloud-Native AI Platform.

RetailOps uses a local-first delivery model. The project proves application, data, Docker, and security behavior locally before introducing AWS, ECR, Terraform, EKS, Helm, and production-style environment promotion.

---

## 1. Current Sprint 9 scope

Sprint 9 establishes the CI/CD foundation before cloud infrastructure exists.

Implemented in this sprint:

- GitHub Actions API CI gate.
- GitHub Actions frontend CI gate.
- Docker Compose full-stack smoke test gate.
- Security CI baseline with secret scanning and vulnerability scanning.
- Root `Makefile` as the shared command layer for local development, GitHub Actions, and Jenkins.
- Jenkins release-confidence pipeline skeleton.
- Disabled placeholder stages for future ECR, Terraform, Kubernetes/EKS, and rollback workflows.

Not implemented yet:

- Real AWS deployment.
- Amazon ECR push.
- Terraform apply.
- Kubernetes/EKS deployment.
- Helm release and rollback.
- Production secrets management.
- Runtime observability stack integration.

The purpose of Sprint 9 is to prove that a change can be tested, built, smoke-tested, scanned, and prepared as a release candidate without pretending that AWS/Kubernetes infrastructure already exists.

---

## 2. Delivery model

RetailOps uses a two-gate CI/CD model:

```text
Local preflight   -> developer confidence before push
GitHub Actions    -> PR/main code confidence gate
Jenkins           -> release confidence and promotion skeleton
Future runtime    -> Kubernetes/EKS deployment and post-deploy validation
```

Tool ownership:

| Layer | Tool | Responsibility |
|---|---|---|
| Local preflight | `Makefile`, Docker Compose, shell scripts | Fast local checks before push or PR |
| Code confidence | GitHub Actions | PR/main validation close to the repository |
| Release confidence | Jenkins | Release-candidate orchestration, evidence, future promotion |
| Runtime confidence | Docker Compose now, Kubernetes/EKS later | Smoke tests, readiness checks, rollout validation |

Decision rule:

```text
GitHub Actions protects the codebase before merge.
Jenkins validates and orchestrates release candidates after merge or release selection.
```

---

## 3. Local command contract

The root `Makefile` is the shared source of truth for repeatable delivery commands.

GitHub Actions and Jenkins should call Make targets instead of duplicating long command sequences in YAML or Groovy.

Common commands:

| Command | Purpose |
|---|---|
| `make install` | Install backend and frontend dependencies |
| `make ci-local` | Run local code-confidence checks |
| `make data-quality` | Generate a synthetic dataset and fail if `quality_report.json` is not `passed` |
| `make compose-ci` | Build and run the full Docker Compose stack, then execute smoke tests |
| `make security-scan` | Run local secret, filesystem, and image security scans |
| `make docker-build` | Build backend and frontend Docker images |
| `make compose-config` | Validate Docker Compose configuration |
| `make compose-down` | Stop and remove local Compose resources |

Recommended local flow before opening a PR:

```bash
make data-quality
make ci-local
make compose-ci
```

`make ci-local` already includes `make data-quality`; running it separately is
useful when working specifically on the synthetic data generator.

Recommended local flow before closing Sprint 9 or preparing portfolio evidence:

```bash
make ci-local
make compose-ci
make security-scan
```

`make security-scan` requires local installations of Trivy and Gitleaks.
`make compose-ci` runs both the base Compose smoke test and the Sprint 9
streaming smoke test.

---

## 4. GitHub Actions workflows

### 4.1 API CI

File:

```text
.github/workflows/api-ci.yml
```

Purpose:

- Start PostgreSQL service.
- Generate demo CSV data.
- Run Alembic migrations.
- Seed demo data.
- Run backend tests.
- Build backend Docker image.

This workflow validates that backend changes remain compatible with the database schema, seed process, and Docker build.

### 4.1a Data CI

File:

```text
.github/workflows/data-ci.yml
```

Purpose:

- Generate a synthetic data profile.
- Run the data quality gate through `make data-quality`.
- Fail when `quality_report.json` is not `passed`.
- Upload data evidence as a GitHub Actions artifact.

Default PR/push profile:

```text
small
```

Manual dispatch can run:

```text
small
medium
```

`medium` is intentionally manual so normal PR checks stay fast.

### 4.2 Frontend CI

File:

```text
.github/workflows/frontend-ci.yml
```

Purpose:

- Install frontend dependencies with `npm ci`.
- Run frontend tests.
- Run linting.
- Build the production frontend bundle.
- Build frontend Docker image.

This workflow validates that UI changes are testable, lint-clean, and production-buildable.

### 4.3 Docker Compose CI

File:

```text
.github/workflows/docker-ci.yml
```

Purpose:

- Validate Docker Compose configuration.
- Build and start the full local stack.
- Wait for database, migration, seed, API, and frontend services.
- Run `scripts/compose_smoke.sh`.
- Upload Compose evidence as a GitHub Actions artifact.
- Clean up Compose resources after the run.

The smoke test validates:

- `GET /health`
- `GET /ready`
- `GET /products`
- `GET /forecasts`
- `GET /dashboard/summary`
- `GET /inventory-risks`
- frontend root availability
- frontend proxy `/api/health`
- frontend proxy `/api/ready`

The evidence is uploaded to the workflow run as an artifact, not committed to the repository.

### 4.4 Security CI

File:

```text
.github/workflows/security-ci.yml
```

Purpose:

- Run Gitleaks secret scanning.
- Run Trivy filesystem vulnerability scanning.
- Run Python dependency audit as a report.
- Run frontend dependency audit as a report.
- Build backend and frontend Docker images.
- Run Trivy image scans.
- Upload security reports as GitHub Actions artifacts.

Initial gate policy:

| Finding type | Current behavior |
|---|---|
| Secret detected | Fail |
| Critical/high filesystem vulnerability | Fail |
| Critical image vulnerability | Fail |
| Python dependency audit findings | Report-only initially |
| NPM audit findings | Report-only initially |

This can be tightened later as the project matures.

---

## 5. Jenkins release-confidence skeleton

File:

```text
Jenkinsfile
```

Sprint 9 Jenkins scope:

- Manual or controlled pipeline execution.
- Local release-candidate validation.
- Reuse of Makefile targets.
- Docker build.
- Docker Compose smoke test.
- Optional security scan if tools are installed on the Jenkins agent.
- Release evidence summary.
- Archive local reports and pipeline artifacts.
- Placeholder stages for future ECR, Terraform, EKS, and rollback work.

Default parameters for Sprint 9:

| Parameter | Recommended Sprint 9 value | Meaning |
|---|---|---|
| `RUN_COMPOSE_SMOKE` | `true` | Validate full local runtime |
| `RUN_SECURITY_SCAN` | `false` initially | Enable after Trivy/Gitleaks exist on Jenkins agent |
| `DEPLOY_TARGET` | `local-only` | Do not deploy to AWS/Kubernetes yet |

Future disabled stages:

- Push to ECR.
- Terraform plan/apply.
- Deploy to Kubernetes/EKS.
- Rollback.

These stages are intentionally not active until the required infrastructure exists.

---

## 6. Evidence and reports

Local and CI reports are written under:

```text
ci-cd/reports/
```

Typical files:

```text
ci-cd/reports/docker-compose-ps.txt
ci-cd/reports/docker-compose-logs.txt
ci-cd/reports/security/gitleaks.json
ci-cd/reports/security/trivy-fs.txt
ci-cd/reports/security/trivy-api-image.txt
ci-cd/reports/security/trivy-frontend-image.txt
ci-cd/reports/jenkins-release-evidence.txt
```

These files are runtime artifacts and should generally not be committed.

Recommended `.gitignore` rule:

```gitignore
# CI/CD local reports and pipeline artifacts
ci-cd/reports/*
!ci-cd/reports/.gitkeep
```

GitHub Actions evidence is stored in the workflow run artifacts section.

Jenkins evidence is archived by the pipeline through `archiveArtifacts`.

---

## 7. Security remediation example

During Sprint 9, the frontend runtime image scan detected critical vulnerabilities in the Nginx Alpine runtime image.

Remediation flow:

```text
Trivy gate detected critical vulnerabilities
-> report was reviewed
-> vulnerable runtime packages were upgraded in the final Nginx image stage
-> frontend image was rebuilt
-> Trivy image scan was rerun
-> scan passed with zero critical findings
```

This demonstrates the expected DevSecOps workflow:

```text
gate -> evidence -> remediation -> rescan -> release confidence
```

---

## 8. How to validate Sprint 9 locally

Run:

```bash
make ci-local
make compose-ci
make security-scan
```

Expected result:

```text
Local CI preflight passed.
Compose smoke test passed.
Streaming smoke test passed.
Security scans passed.
```

If these pass locally, push the branch and validate the GitHub Actions workflows.

---

## 9. How to validate Sprint 9 in GitHub Actions

After pushing a branch or opening a PR, check:

```text
GitHub -> Actions
```

Expected workflow status:

- API CI: pass.
- Frontend CI: pass.
- Docker Compose CI: pass.
- Security CI: pass.

Download artifacts from individual workflow runs when evidence is needed for portfolio documentation or troubleshooting.

---

## 10. How to validate Sprint 9 in Jenkins

Create a Jenkins Pipeline job using:

```text
Pipeline script from SCM
Script Path: Jenkinsfile
```

Recommended first run:

```text
RUN_COMPOSE_SMOKE = true
RUN_SECURITY_SCAN = false
DEPLOY_TARGET = local-only
```

Recommended second run after installing Trivy and Gitleaks on the Jenkins agent:

```text
RUN_COMPOSE_SMOKE = true
RUN_SECURITY_SCAN = true
DEPLOY_TARGET = local-only
```

Expected Jenkins result:

- Local CI gate passes.
- Docker images build.
- Docker Compose smoke test passes.
- Optional security scan passes.
- Release evidence summary is archived.

---

## 11. Troubleshooting

### Security scan fails but terminal does not show vulnerability details

Check generated reports:

```bash
cat ci-cd/reports/security/trivy-fs.txt
cat ci-cd/reports/security/trivy-api-image.txt
cat ci-cd/reports/security/trivy-frontend-image.txt
cat ci-cd/reports/security/gitleaks.json
```

### Compose smoke test fails

Check:

```bash
docker compose ps
docker compose logs --no-color
```

Then rerun:

```bash
make compose-ci
```

### Local security scan cannot start

Install required tools:

```bash
brew install trivy gitleaks
```

Then rerun:

```bash
make security-scan
```

### Jenkins security scan fails immediately

Confirm that Trivy and Gitleaks are installed on the Jenkins agent.

If they are not installed, run Jenkins with:

```text
RUN_SECURITY_SCAN = false
```

until the Jenkins agent is prepared.

---

## 12. Sprint 9 Definition of Done

Sprint 9 is considered complete when:

- `make ci-local` passes locally.
- `make compose-ci` passes locally, including base Compose and streaming smoke checks.
- `make security-scan` passes locally.
- API CI passes in GitHub Actions.
- Frontend CI passes in GitHub Actions.
- Docker Compose CI passes in GitHub Actions.
- Security CI passes in GitHub Actions.
- Jenkins pipeline runs successfully in local-only mode.
- Jenkins archives release evidence.
- Cloud deployment stages are explicitly marked as disabled/future scope.
- Reports are stored as artifacts, not committed as normal source files.

---

## 13. Future evolution

Future sprints will extend this foundation:

| Future area | Planned maturity |
|---|---|
| Terraform | `fmt`, `validate`, `plan`, controlled apply |
| AWS | IAM, ECR, secrets, networking, cost controls |
| ECR | Versioned image publishing from Jenkins |
| EKS | Kubernetes deployment target |
| Helm | Release packaging and rollback |
| Observability | Post-deploy metrics, logs, dashboards, alerts |
| DevSecOps | SBOM, provenance, policy-as-code, stricter vulnerability gates |
| MLOps | Model evaluation, model promotion, model rollback evidence |

Until those foundations exist, Jenkins remains a local release-confidence pipeline skeleton rather than a real cloud deployment pipeline.
