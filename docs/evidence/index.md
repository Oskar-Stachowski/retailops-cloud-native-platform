# Evidence Index

Last reviewed: 2026-05-12

This index maps tracked evidence to what it proves. It avoids treating documentation claims, roadmap diagrams, or target architecture text as proof of implementation.

| Category | File path | What it proves | Related area | Audience | Last validation note |
|---|---|---|---|---|---|
| Evidence governance | `docs/evidence/README.md` | Evidence layer has a documented purpose and split between curated evidence and raw reports. | Documentation | Recruiter-facing | Updated during evidence cleanup. |
| Evidence governance | `docs/evidence/evidence-folder-map.md` | Final evidence structure and expected folder usage are documented. | Documentation | Internal and reviewer-facing | Updated during evidence cleanup. |
| Evidence governance | `docs/evidence/gitignore-evidence-policy.md` | Repository has explicit rules for tracked versus ignored evidence. | Git hygiene | Internal | Matched against root `.gitignore`. |
| API | `docs/evidence/api/README.md` | API evidence folder is indexed for reviewer navigation. | Backend/API | Recruiter-facing | Added for API-001 and API-009 evidence. |
| API | `docs/evidence/api/startup-log.md` | FastAPI starts under Uvicorn and responds to `/health`. | Backend/API | Recruiter-facing | Captured from local Uvicorn run on `127.0.0.1:8011`. |
| API | `docs/evidence/api/openapi-snapshot.json` | Running API exposes a concrete OpenAPI schema at `/openapi.json`. | Backend/API | Technical reviewer | Captured with `curl` and formatted with `jq`. |
| Docker | `docs/evidence/docker/README.md` | Docker evidence folder is indexed for reviewer navigation. | Docker, local runtime | Recruiter-facing | Added for DOCKER-001, DOCKER-002 and DOCKER-005 evidence. |
| Docker | `docs/evidence/docker/compose-ci-smoke.md` | Backend and frontend images build; full Compose stack starts; API/frontend/streaming/observability smoke tests pass; cleanup runs. | Docker, Compose, local runtime | Recruiter-facing | Captured from `make compose-ci`. |
| AWS/Terraform | `docs/evidence/aws/README.md` | AWS showcase evidence is indexed and linked to raw Terraform snapshots. | Terraform, AWS, FinOps | Recruiter-facing | Updated after moving raw Terraform reports to `ci-cd/reports/iac/`. |
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
| Kubernetes raw report | `ci-cd/reports/k8s/kubernetes-secret-scan-snapshot.txt` | Kubernetes manifests and secret examples were scanned with Gitleaks and no leaks were found. | Kubernetes, Security | Reviewer-facing raw snapshot | Captured from `gitleaks detect --source k8s --no-git --redact --verbose`. |
| Jenkins | `docs/evidence/jenkins/README.md` | Jenkins evidence is indexed and separated from raw pipeline reports. | Jenkins, CI/CD | Recruiter-facing | Added during evidence cleanup. |
| Jenkins | `docs/evidence/jenkins/jenkins-stage-view.png` | Jenkins pipeline stage view existed for release-confidence evidence. | Jenkins, CI/CD | Recruiter-facing | Static screenshot; should be refreshed after next successful Jenkins run. |
| Jenkins | `docs/evidence/jenkins/jenkins-status-and-artifacts.png` | Jenkins status and archived artifact view existed. | Jenkins, CI/CD | Recruiter-facing | Static screenshot; should be refreshed after next successful Jenkins run. |
| Security raw report | `ci-cd/reports/security/trivy-fs-snapshot.txt` | Filesystem dependency scan found 0 vulnerabilities in the captured snapshot. | Security, supply chain | Reviewer-facing raw snapshot | Trivy snapshot shows 0 vulnerabilities for lockfiles. |
| Security raw report | `ci-cd/reports/security/trivy-api-image-snapshot.txt` | API image vulnerability scan was executed and showed no vulnerabilities in the captured snapshot. | Security, Docker | Reviewer-facing raw snapshot | Long Trivy output; use as scan evidence, not a permanent guarantee. |
| Security raw report | `ci-cd/reports/security/trivy-frontend-image-snapshot.txt` | Frontend image scan was executed and found critical vulnerabilities in the captured snapshot. | Security, Docker | Internal until fixed | Evidence of scanning maturity, but not a clean result. |
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
