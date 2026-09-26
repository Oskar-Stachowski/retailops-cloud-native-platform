# Evidence Index

Last reviewed: 2026-05-18

CI governance and dependency validation evidence refreshed: 2026-09-25. Registry, local Kubernetes, Terraform state/drift, monitoring and actual Jenkins evidence added: 2026-09-26. Other evidence retains its original capture dates.

This index maps tracked evidence to what it proves. It avoids treating documentation claims, roadmap diagrams, or target architecture text as proof of implementation.

## Evidence Refresh Ledger

Use this table as the first stop when reviewing freshness. It records the last captured date, repository commit, validation command, expected outcome, environment, and the tracked artifact.

| Date | Commit SHA | Command run | Expected outcome | Environment | Artifact |
|---|---|---|---|---|---|
| 2026-09-26 | Jenkins `5b3fc7ab1dca68e63f3e3f3f91548adbaba51855`; CI merge `ef9b5974f3b360e3f7ff996363727ad54cfa0a64` | `make compose-ci`; Jenkins build 4; Required CI `36251803830` | Live samples/Grafana queries, real two-minute alert firing/resolution, scoped cleanup and 24 successful CI jobs; no 30-day compliance or external notification claim. | Local Jenkins ARM64 and GitHub AMD64 disposable stacks | [Monitoring report](observability/2026-09-26-validation.md), [Jenkins report](jenkins/2026-09-26-validation.md) |
| 2026-09-26 | Local `e729ee82e72d0934b77c2a632297d92fa02fec04`; PR head `3266c80ef96868644697fcf6c0090bd6e9285e99`; merged main `beae2b19abf6a39edb0bc2155baa85a0a887a3d4` | Account inventory, guarded baseline, `make terraform-state-test`; Required CI `36243524269`; OIDC workflow `36244078945` | Baseline distinguished from drift, state/account guards, local migration and out-of-band drift checks, 24 CI jobs; S3 backend remains unactivated. | AWS eu-central-1 inventory and plan only; local ARM64 and CI AMD64 Terraform tests | [Terraform state/drift report](aws/2026-09-26-state-drift.md) |
| 2026-09-26 | Local `344919494015f086b333c0c2e1a4f875e8e68d94`; CI test merge `423a1eab57eb584840260cd01fe2c9066ae0728f`; merged main `aa69c1e25f71e11034666f91057308454ba5d430` | `make k8s-runtime-drill`; Required CI run `36240218438` | All 24 CI jobs and five runtime stages passed; jobs, ingress, NetworkPolicy, streaming deduplication, PVC retention, readiness, browser checks, update/rollback and cleanup verified. | Separate local ARM64 and GitHub-hosted AMD64 kind clusters, demo data | [Kubernetes runtime report](kubernetes/2026-09-26-runtime.md) |
| 2026-09-26 | `d8897822b6c2cbabcc14ee34fd7985b863aea8bd` | Verified registry release run `36227222222` | Exact tested images published to GHCR; signed manifest, four provenance and four SPDX attestations verified; fresh-runner digest pulls and rollback passed; annotated v0.2.1 and durable evidence published. | GitHub-hosted Linux AMD64, two isolated demo DB drills, Chromium | [Registry release report](releases/2026-09-26-registry.md) |
| 2026-09-25 | `977c776ed7cf80ae2229e1522dba8a44e3827a75` | `PLAYWRIGHT_BROWSER_CHANNEL=chrome make release-drill` | Baseline/update/rollback passed HTTP, browser and data checks; HTTP 502 fault detected; new-version write preserved; migration refusals and cleanup passed. | Isolated local Docker, ARM64, demo data, Chrome | [Versioned rollback report](releases/README.md) |
| 2026-09-25 | `21e916580f8c1e4604e98d3fb8c249aea94f91c8` | `make db-recovery-drill` | 15 tables / 66 rows identical after restore; three decisions and five idempotent actions retained; four invalid backup cases rejected; cleanup passed. | Isolated local Docker project, PostgreSQL 16.13, demo fixture | [Database recovery report](db/README.md) |
| 2026-09-25 | PR head `854d315de3127f5bd0c6a997b064414b6e285d67`; merged main `2154a2f` | Required CI run `36138113369` | 23 jobs passed, including seven critical Chromium journeys in 16.3 seconds without retries or skips. | GitHub Actions, demo-seeded PostgreSQL, Docker Compose, Chromium | [Browser validation and artifact](e2e/README.md) |
| 2026-09-25 | PR head `4d41c93dbcb90e598cbed4f3adc3b785d82d9567`; merged main `44f7404` | Required CI run `36133335007` | All 23 jobs passed; 302 API tests, 83.82% coverage, 36 frontend tests; scans and Compose smoke passed their documented gates. | GitHub Actions, seeded PostgreSQL, Docker Compose | [Dated validation and artifact links](github-actions/2026-09-25-validation.md) |
| 2026-09-25 | `46218000c78e49edca6ec396bbfa2314a1645be2` | Authenticated GitHub REST `GET .../branches/main` and `GET .../branches/main/protection` | Active PR and status-check protection, administrator enforcement, force pushes and deletion disabled. | GitHub repository settings | [Branch protection snapshot and notes](github/README.md) |
| 2026-05-18 | `5aedb2bdc7d7` | `make compose-ci` | Backend and frontend images build, Compose stack starts, API/frontend/streaming/observability smoke checks pass, cleanup completes. | Local Docker / Docker Compose | [`docs/evidence/docker/compose-ci-smoke.md`](docker/compose-ci-smoke.md) |
| 2026-05-18 | `5aedb2bdc7d7` | `make compose-up && make runtime-smoke-evidence && make compose-down` | Running local stack passes API/frontend smoke, k6 API p95 baseline and Playwright browser smoke. | Local Docker / Docker Compose / k6 / Playwright | [`docs/evidence/runtime/local-runtime-smoke.md`](runtime/local-runtime-smoke.md) |
| 2026-05-12 | `e4d0eb72f6a9c17e5072ca7954e1df03b06f8630` | `cd services/api && PYTHONPATH=. .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8011` | API starts cleanly; `/health` returns `200`; `/openapi.json` is captured. | Local Python / loopback HTTP | [`docs/evidence/api/startup-log.md`](api/startup-log.md) |
| 2026-05-17 | `38cab9839f2c` | `make sbom-repository SBOM_SOURCE_VERSION=38cab9839f2c` | Repository SBOM snapshots are generated in SPDX, CycloneDX and Syft table formats. | Local Syft 1.44.0 | [`docs/evidence/security/sbom-provenance-evidence.md`](security/sbom-provenance-evidence.md) |
| 2026-01-31 | `legacy-capture` | `PYTHONPATH=. services/api/.venv/bin/python -m ml.models.random_forest_forecast --profile small --window-days 28 --holdout-days 7 --n-estimators 20 --output-dir /private/tmp/retailops-rf-evidence` | RandomForest evidence artifacts are generated and beat the moving-average baseline on the tracked holdout set. | Local Python / temporary output directory | [`docs/evidence/ml/random-forest-v1/README.md`](ml/random-forest-v1/README.md) |
| Sprint 10 showcase | `legacy-capture` | `terraform destroy` for the temporary AWS showcase environment | Temporary showcase AWS resources are removed and the destroy snapshot is retained. | Temporary AWS showcase account | [`docs/evidence/aws/aws-cleanup-confirmation.md`](aws/aws-cleanup-confirmation.md) |

## Evidence Refresh Workflow

Use the same refresh pattern when an artifact becomes stale:

1. Run the documented command from the relevant evidence README or report.
2. Sanitize output if it contains account identifiers, machine-specific paths, or volatile IDs.
3. Update the tracked artifact or snapshot in place.
4. Add or refresh the row in the ledger above with the capture date and commit SHA.
5. Update the validation note in the main inventory table below if reviewer expectations changed.

| Category | File path | What it proves | Related area | Audience | Last validation note |
|---|---|---|---|---|---|
| Evidence governance | `docs/evidence/README.md` | Evidence layer has a documented purpose and split between curated evidence and raw reports. | Documentation | Recruiter-facing | Updated during evidence cleanup. |
| Evidence governance | `docs/evidence/evidence-folder-map.md` | Final evidence structure and expected folder usage are documented. | Documentation | Internal and reviewer-facing | Updated during evidence cleanup. |
| Evidence governance | `docs/evidence/gitignore-evidence-policy.md` | Repository has explicit rules for tracked versus ignored evidence. | Git hygiene | Internal | Matched against root `.gitignore`. |
| CI governance | `docs/governance/github-actions-ci.md` | GitHub Actions workflows, composite actions, evidence paths, and known CI boundaries are mapped to the readiness checklist. | GitHub Actions, CI/CD | Reviewer-facing | Added during GitHub Actions CI readiness update. |
| CI governance | `docs/governance/branch-protection.md`, `docs/evidence/github/` | Active `main` protection and the exact required GitHub Actions check are documented with an API snapshot. | GitHub Actions, branch protection | Reviewer-facing | Enabled and independently read back on 2026-09-25, with enforcement for administrators. |
| API | `docs/evidence/api/README.md` | API evidence folder is indexed for reviewer navigation. | Backend/API | Recruiter-facing | Added for API-001 and API-009 evidence. |
| API | `docs/evidence/api/startup-log.md` | FastAPI starts under Uvicorn and responds to `/health`. | Backend/API | Recruiter-facing | Captured from local Uvicorn run on `127.0.0.1:8011`. |
| API | `docs/evidence/api/openapi-snapshot.json` | Running API exposes a concrete OpenAPI schema at `/openapi.json`. | Backend/API | Technical reviewer | Captured with `curl` and formatted with `jq`. |
| Docker | `docs/evidence/docker/README.md` | Docker evidence folder is indexed for reviewer navigation. | Docker, local runtime | Recruiter-facing | Added for DOCKER-001, DOCKER-002 and DOCKER-005 evidence. |
| Docker | `docs/evidence/docker/compose-ci-smoke.md` | Backend and frontend images build; full Compose stack starts; API/frontend/streaming/observability smoke tests pass; cleanup runs. | Docker, Compose, local runtime | Recruiter-facing | Refreshed from `make compose-ci` on commit `5aedb2bdc7d7`. |
| E2E evidence | `docs/evidence/e2e/README.md` | Playwright-based connected frontend/API evidence capture is documented with prerequisites, output paths and claim boundary. | Frontend, API, testing | Recruiter and technical reviewer | Added for `make evidence-frontend-api`; generated screenshots land in `docs/evidence/frontend-api/`. |
| E2E evidence | `docs/evidence/frontend-api/` | Full-page screenshots captured from connected frontend pages. | Frontend, API, testing | Recruiter-facing | Generated by `make evidence-frontend-api`; not pixel-perfect visual regression evidence. |
| Runtime smoke | `docs/evidence/runtime/README.md` | Runtime smoke evidence folder is indexed for reviewer navigation. | Docker, API, frontend, testing | Recruiter-facing | Added for local k6 and Playwright runtime smoke evidence. |
| Runtime smoke | `docs/evidence/runtime/local-runtime-smoke.md` | Running local stack passed API/frontend smoke, k6 API smoke baseline and Playwright browser smoke. | Docker, API, frontend, testing | Recruiter and technical reviewer | Captured from `make runtime-smoke-evidence`; k6 p95 `34.19 ms`, failed HTTP requests `0.00%`, Playwright `1/1` passed. |
| ML/MLOps | `docs/evidence/ml/README.md` | ML evidence folder is indexed for reviewer navigation. | ML, MLOps | Recruiter-facing | Added for trained RandomForest demand model evidence. |
| ML/MLOps | `docs/evidence/ml/random-forest-v1/README.md` | RandomForest training command, metrics, baseline comparison, and evidence file map are documented. | ML, MLOps | Recruiter-facing | Captured from local `ml.models.random_forest_forecast` run. |
| ML/MLOps | `docs/evidence/ml/random-forest-v1/metrics.json` | Trained RandomForest model beat the moving-average baseline on WAPE and was marked `candidate`. | ML, MLOps | Technical reviewer | WAPE `72.1146` vs baseline `81.0797`, improvement `11.0571%`. |
| ML/MLOps | `docs/evidence/ml/random-forest-v1/random_forest_model.joblib` | Serialized scikit-learn model artifact exists for the trained demand forecast model. | ML, MLOps | Technical reviewer | SHA-256 tracked in `checksums.sha256`. |
| ML/MLOps | `docs/evidence/ml/random-forest-v1/predictions.csv` | Time-based holdout predictions include trained model, baseline prediction, and actual values. | ML, MLOps | Technical reviewer | 991 evaluated holdout rows plus header. |
| ML/MLOps | `docs/evidence/ml/random-forest-v1/feature_importance.csv` | RandomForest feature importance report exists for model interpretability evidence. | ML, MLOps | Technical reviewer | Top features include `unit_price`, `rolling_mean_units`, `lag_1_units`. |
| AWS/Terraform | `docs/evidence/aws/README.md` | AWS showcase evidence is indexed and linked to raw Terraform snapshots. | Terraform, AWS, FinOps | Recruiter-facing | Updated after moving raw Terraform reports to `ci-cd/reports/iac/`. |
| AWS/Terraform state | `docs/evidence/aws/2026-09-26-state-drift.md`, `2026-09-26-state-drift.json` | Scoped account inventory, guarded baseline/OIDC planning, tested drift classification and prepared backend controls. | Terraform, state, CI/CD | Technical reviewer | 2026-09-26; no active state or matching bucket found, so no live AWS migration or no-drift claim. |
| AWS/Terraform | `docs/evidence/aws/aws-cleanup-confirmation.md` | Temporary AWS showcase resources were destroyed and cleanup was documented. | Terraform, AWS, FinOps | Recruiter-facing | Linked to tracked destroy snapshot. |
| AWS/Terraform | `docs/evidence/aws/aws-console-vpc.png` | AWS Console screenshot for VPC/networking resources. | AWS networking | Recruiter-facing | Static screenshot; freshness depends on original capture. |
| AWS/Terraform | `docs/evidence/aws/aws-console-ecr.png` | AWS Console screenshot for ECR repositories. | AWS ECR, CI/CD target | Recruiter-facing | Static screenshot; freshness depends on original capture. |
| AWS/Terraform | `docs/evidence/aws/aws-console-iam.png` | AWS Console screenshot for IAM baseline resources. | AWS IAM | Recruiter-facing | Static screenshot; freshness depends on original capture. |
| AWS/Terraform | `docs/evidence/aws/aws-console-budget.png` | AWS Console screenshot for budget/cost guardrail. | FinOps, AWS Budget | Recruiter-facing | Static screenshot; freshness depends on original capture. |
| AWS/Terraform | `docs/evidence/aws/aws-console-cloudwatch.png` | AWS Console screenshot for CloudWatch log groups. | Observability, AWS | Recruiter-facing | Static screenshot; freshness depends on original capture. |
| AWS/Terraform raw report | `ci-cd/reports/iac/sprint-10-terraform-validate.txt` | Terraform configuration validated successfully. | Terraform | Reviewer-facing raw snapshot | Contains `Success! The configuration is valid.` |
| AWS/Terraform raw report | `ci-cd/reports/iac/sprint-10-terraform-plan-dev.txt` | Sanitized dev foundation plan summary: 24 add, 0 change, 0 destroy. | Terraform, AWS | Reviewer-facing raw snapshot | Sanitized summary; not full raw plan. |
| AWS/Terraform raw report | `ci-cd/reports/iac/sprint-10-terraform-apply.txt` | Sanitized apply evidence for the temporary AWS showcase. | Terraform, AWS | Reviewer-facing raw snapshot | Sanitized summary; account identifiers removed. |
| AWS/Terraform raw report | `ci-cd/reports/iac/sprint-10-terraform-destroy.txt` | Sanitized destroy evidence for the temporary AWS showcase. | Terraform, AWS, FinOps | Reviewer-facing raw snapshot | Sanitized summary; account identifiers removed. |
| Kubernetes raw report | `ci-cd/reports/k8s/kubernetes-smoke-snapshot.txt` | Base and dev Kustomize manifests render, parse, pass kubeconform validation, and include expected workload resources. | Kubernetes | Reviewer-facing raw snapshot | Captured from `make k8s-smoke`. |
| Kubernetes runtime | `docs/evidence/kubernetes/2026-09-26-runtime.md`, `2026-09-26-runtime.json` | Actual local deployment, persistent data through restarts/update/rollback, ingress, enforced NetworkPolicy, streaming and browser behavior. | Kubernetes, release, recovery | Technical reviewer | Clean ARM64/AMD64 runs and all 24 CI jobs passed on 2026-09-26; source/report hashes and image identities retained. |
| Kubernetes raw report | `ci-cd/reports/k8s/kubernetes-secret-scan-snapshot.txt` | Kubernetes manifests and secret examples were scanned with Gitleaks and no leaks were found. | Kubernetes, Security | Reviewer-facing raw snapshot | Captured from `gitleaks detect --source k8s --no-git --redact --verbose`. |
| Observability | `docs/evidence/observability/2026-09-26-validation.md`, `2026-09-26-validation.json` | Actual metrics/Grafana queries, alert transitions and cleanup on ARM64 and AMD64. | Monitoring, SLO | Technical reviewer | Dated execution with exact source, image IDs and artifact hashes; short local drill only. |
| Jenkins execution | `docs/evidence/jenkins/2026-09-26-validation.md`, `2026-09-26-validation.json` | Actual pipeline stages and archived source identity. | Jenkins, CI | Technical reviewer | SUCCESS; 271 backend tests passed, 40 skipped, 76% coverage and mandatory runtime incident drill. |
| Jenkins | `docs/evidence/jenkins/README.md` | Jenkins evidence is indexed and separated from raw pipeline reports. | Jenkins, CI/CD | Recruiter-facing | Added during evidence cleanup. |
| Jenkins | `docs/evidence/jenkins/jenkins-stage-view.png` | Jenkins pipeline stage view existed for release-confidence evidence. | Jenkins, CI/CD | Recruiter-facing | Historical screenshot preserved; current execution is recorded in the dated Jenkins report. |
| Jenkins | `docs/evidence/jenkins/jenkins-status-and-artifacts.png` | Jenkins status and archived artifact view existed. | Jenkins, CI/CD | Recruiter-facing | Historical screenshot preserved; current execution is recorded in the dated Jenkins report. |
| Security raw report | `ci-cd/reports/security/trivy-fs-snapshot.txt` | Filesystem dependency scan found 0 vulnerabilities in the captured snapshot. | Security, supply chain | Reviewer-facing raw snapshot | Trivy snapshot shows 0 vulnerabilities for lockfiles. |
| Security raw report | `ci-cd/reports/security/trivy-api-image-snapshot.txt` | API image vulnerability scan was executed and showed no vulnerabilities in the captured snapshot. | Security, Docker | Reviewer-facing raw snapshot | Long Trivy output; use as scan evidence, not a permanent guarantee. |
| Security raw report | `ci-cd/reports/security/trivy-frontend-image-snapshot.txt` | Historical frontend image scan found critical vulnerabilities. | Security, Docker | Historical | Preserved as originally captured; superseded for current status by the [2026-09-25 CI results](github-actions/2026-09-25-validation.md). |
| Security | `docs/evidence/security/README.md` | Security evidence folder is indexed and reviewer-facing. | Security, supply chain | Recruiter-facing | Added with SBOM evidence promotion. |
| Security | `docs/evidence/security/sbom-provenance-evidence.md` | Syft repository SBOM snapshots exist, provenance workflow scope is clear, and signing is not overclaimed. | SBOM, provenance, signing boundary | Recruiter and technical reviewer | Captured with `make sbom-repository SBOM_SOURCE_VERSION=38cab9839f2c`; SPDX has 76 packages and CycloneDX has 96 components. |
| SBOM raw report | `ci-cd/reports/sbom/retailops-repository-sbom-spdx-snapshot.json` | Repository dependency inventory exists in SPDX JSON format. | SBOM, supply chain | Technical reviewer | Generated by Syft 1.44.0 from `dir:.` with local/cache folders excluded. |
| SBOM raw report | `ci-cd/reports/sbom/retailops-repository-sbom-cyclonedx-snapshot.json` | Repository dependency inventory exists in CycloneDX JSON format. | SBOM, supply chain | Technical reviewer | Generated by Syft 1.44.0 from `dir:.`; CycloneDX 1.6. |
| SBOM raw report | `ci-cd/reports/sbom/retailops-repository-sbom-summary-snapshot.txt` | Human-readable dependency inventory summary exists for quick review. | SBOM, supply chain | Recruiter-facing summary | Generated by Syft table output. |
| Provenance raw report | `ci-cd/reports/provenance/provenance-ci.evidence.md` | GitHub Actions provenance workflow behavior and claim boundary are documented. | Provenance, supply chain | Technical reviewer | Workflow exists; fresh GitHub attestation run should be captured separately before stronger release claims. |
| Architecture images | `docs/evidence/gptimages-index.md` | Generated architecture images have usage status and recommended actions. | Documentation, diagrams | Internal and reviewer-facing | Added during GPTimages review. |
| Architecture images | `GPTimages/Architecture.png` | High-level architecture visual used in README and case study. | Architecture | Recruiter-facing | Current as conceptual overview; not implementation proof. |
| Architecture images | `GPTimages/CI-CD-Pipeline-Delivery-Workflow.png` | CI/CD delivery workflow visual used in README and case study. | CI/CD | Recruiter-facing | Current as delivery concept; pair with workflows and Jenkinsfile. |
| Architecture images | `GPTimages/Data-Flow.png` | Generated data-flow image exists but is not referenced by tracked docs. | Documentation | Internal | Unused; keep as archive until replaced or deleted in a later cleanup. |
| Architecture images | `GPTimages/Future-Growth-Perspective.png` | Generated future-growth image exists but is not referenced by tracked docs. | Documentation | Internal | Unused; keep as archive until a future narrative needs it. |

## Evidence Not Yet Tracked

The following local report areas exist but are intentionally ignored because they are volatile, machine-generated, or need sanitization before becoming portfolio evidence:

- `ci-cd/reports/api/coverage.xml`
- `ci-cd/reports/data/generated/`
- `ci-cd/reports/observability/`
- `ci-cd/reports/ruff/`
- `ci-cd/reports/security/gitleaks.json`
- non-snapshot files under `ci-cd/reports/iac/` and `ci-cd/reports/security/`

When one of these outputs should become recruiter-facing evidence, create a small sanitized `*-snapshot.txt`, `*-snapshot.json`, `*.evidence.md`, or README/index entry and link it from this file.
