# Evidence Folder Map

Last reviewed: 2026-05-12

## Final Structure

```text
docs/evidence/
├── README.md
├── index.md
├── api/
│   ├── README.md
│   ├── startup-log.md
│   └── openapi-snapshot.json
├── aws/
│   ├── README.md
│   ├── aws-cleanup-confirmation.md
│   └── aws-console-*.png
├── docker/
│   ├── README.md
│   └── compose-ci-smoke.md
├── jenkins/
│   ├── README.md
│   ├── jenkins-stage-view.png
│   └── jenkins-status-and-artifacts.png
├── gptimages-index.md
├── gitignore-evidence-policy.md
├── evidence-folder-map.md
└── evidence-cleanup-report.md

ci-cd/reports/
├── README.md
├── iac/
│   ├── README.md
│   └── sprint-10-terraform-*.txt
└── security/
    ├── README.md
    └── trivy-*-snapshot.txt
```

## Folder Responsibilities

| Folder | Purpose | Commit | Do not commit |
|---|---|---|---|
| `docs/evidence/` | Curated reviewer-facing evidence, indexes, cleanup reports, diagrams, screenshots. | Sanitized screenshots, Markdown summaries, evidence maps. | Raw logs, secrets, local cache output, generated datasets. |
| `docs/evidence/api/` | API startup and OpenAPI schema evidence. | Startup notes and generated OpenAPI snapshots. | Raw server logs with sensitive values or local-only debug dumps. |
| `docs/evidence/aws/` | Human-readable AWS/Terraform showcase screenshots and cleanup notes. | Sanitized console screenshots and cleanup notes. | Full raw Terraform logs, account IDs, ARNs, console URLs. |
| `docs/evidence/docker/` | Docker build and Compose smoke evidence. | Sanitized build and smoke summaries. | Full raw Compose logs, large runtime dumps, local-only container state. |
| `docs/evidence/jenkins/` | Curated Jenkins UI screenshots and notes. | Screenshot evidence with no secrets or private URLs. | Raw Jenkins logs unless sanitized. |
| `ci-cd/reports/` | Raw or semi-raw generated reports from automation. | README files and explicit sanitized snapshots. | Volatile local logs, coverage XML, generated datasets, raw scanner dumps. |
| `ci-cd/reports/iac/` | Terraform, Checkov, TFLint, drift, and IaC report outputs. | Sanitized snapshots and report README. | Terraform state, binary plans, `.terraform/`, unsanitized plan/apply logs. |
| `ci-cd/reports/security/` | Trivy, Gitleaks, dependency audit outputs. | Sanitized snapshots and report README. | Unsanitized secret scan outputs and non-snapshot scanner files. |
| `GPTimages/` | Generated architecture visuals used by README, case study, and docs. | Stable images referenced by documentation. | New unindexed generated images. |

## Curated vs Raw Evidence

```mermaid
flowchart LR
    subgraph CURATED["docs/evidence"]
      IDX[index.md]
      AWS[AWS screenshots and cleanup notes]
      JENKINS[Jenkins screenshots]
      POLICY[Evidence policy and folder map]
    end

    subgraph RAW["ci-cd/reports"]
      IAC[Terraform snapshots]
      SEC[Trivy snapshots]
      LOCAL[Ignored local reports]
    end

    RAW --> IDX
    AWS --> IDX
    JENKINS --> IDX
    POLICY --> IDX
```

## AWS and Terraform Evidence Flow

```mermaid
flowchart TD
    TF[Terraform modules and dev environment] --> VALIDATE[terraform validate]
    VALIDATE --> PLAN[terraform plan]
    PLAN --> APPLY[controlled temporary apply]
    APPLY --> SCREENSHOTS[AWS Console screenshots]
    APPLY --> DESTROY[terraform destroy]
    DESTROY --> CLEANUP[cleanup confirmation]

    VALIDATE --> IAC1[ci-cd/reports/iac/sprint-10-terraform-validate.txt]
    PLAN --> IAC2[ci-cd/reports/iac/sprint-10-terraform-plan-dev.txt]
    APPLY --> IAC3[ci-cd/reports/iac/sprint-10-terraform-apply.txt]
    DESTROY --> IAC4[ci-cd/reports/iac/sprint-10-terraform-destroy.txt]
    SCREENSHOTS --> AWS[docs/evidence/aws/*.png]
    CLEANUP --> AWSDOC[docs/evidence/aws/aws-cleanup-confirmation.md]
```

## CI/CD Evidence Flow

```mermaid
flowchart LR
    MAKE[Makefile targets] --> LOCAL[Local reports]
    GHA[GitHub Actions] --> ARTIFACTS[CI artifacts]
    JENKINS[Jenkinsfile] --> JREPORT[ci-cd/reports/jenkins-release-evidence.txt]
    LOCAL --> REPORTS[ci-cd/reports]
    ARTIFACTS --> REPORTS
    JREPORT --> REPORTS
    REPORTS --> SNAPSHOTS[Sanitized snapshots]
    SNAPSHOTS --> INDEX[docs/evidence/index.md]
```

## Security Evidence Flow

```mermaid
flowchart LR
    GITLEAKS[Gitleaks] --> RAWSECRET[ignored raw gitleaks.json]
    TRIVYFS[Trivy filesystem] --> FSSNAP[trivy-fs-snapshot.txt]
    TRIVYAPI[Trivy API image] --> APISNAP[trivy-api-image-snapshot.txt]
    TRIVYFE[Trivy frontend image] --> FESNAP[trivy-frontend-image-snapshot.txt]
    FSSNAP --> SECIDX[ci-cd/reports/security/README.md]
    APISNAP --> SECIDX
    FESNAP --> SECIDX
    SECIDX --> INDEX[docs/evidence/index.md]
```

## Observability Evidence Flow

```mermaid
flowchart LR
    PROM[Prometheus queries] --> LOCALOBS[ci-cd/reports/observability ignored]
    GRAFANA[Grafana dashboards] --> LOCALOBS
    RUNBOOK[docs/runbooks/observability-runbook.md] --> LOCALOBS
    LOCALOBS --> FUTURE[Future sanitized dashboard snapshots]
    FUTURE --> INDEX[docs/evidence/index.md]
```

## Kubernetes and Helm Evidence Flow

```mermaid
flowchart LR
    K8S[k8s manifests] --> VALIDATE[future kubeconform or kubectl dry-run]
    HELM[future Helm chart] --> LINT[future helm lint]
    VALIDATE --> REPORTS[ci-cd/reports/kubernetes future]
    LINT --> REPORTS
    REPORTS --> INDEX[docs/evidence/index.md]
```

## MLOps and GenAI Evidence Flow

```mermaid
flowchart LR
    ML[ml/ and data docs] --> EVAL[future model/data evaluation report]
    GENAI[future GenAI use case] --> SAFETY[future safety and prompt evidence]
    EVAL --> REPORTS[ci-cd/reports/ml future]
    SAFETY --> REPORTS
    REPORTS --> INDEX[docs/evidence/index.md]
```
