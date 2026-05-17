# Security

This directory contains the security and DevSecOps configuration currently used by the RetailOps platform.

## Implemented Controls

| Area | Implementation |
|---|---|
| Secret scanning | Gitleaks configuration and GitHub Actions workflow |
| Filesystem and image vulnerability scanning | Trivy local targets and Security CI jobs |
| Python dependency audit | `pip-audit` evidence in Security CI |
| Frontend dependency audit | `npm audit` evidence in Security CI |
| Terraform linting | TFLint configuration for IaC quality gates |
| Terraform policy scanning | Checkov configuration for IaC security reports |
| Critical IaC guardrails | Makefile and CI checks for IAM users, access keys, AdministratorAccess, and wildcard IAM actions |

## Current Policy

Security checks are split into hard gates and evidence-generating reports:

- Gitleaks and Trivy filesystem scans are blocking checks.
- TFLint is a blocking IaC quality gate.
- Checkov is currently report-only, with explicit Makefile guardrails enforcing critical IAM and secret patterns.
- Dependency audit jobs generate evidence and should be promoted to blocking gates after baseline cleanup.

## Accepted IaC Exception

`CKV_AWS_356` is skipped in `security/iac/checkov.yml` for the Terraform plan read-only discovery policy. The policy intentionally uses wildcard resources only for AWS `Get`, `List`, and `Describe` actions required by Terraform plan. It does not grant create, update, delete, pass-role, or administrator permissions. The Makefile guardrails still block wildcard IAM actions and privileged policy patterns.

## Accepted Checkov Findings

Checkov is intentionally kept as a report-only control at this stage. The remaining findings are not automatically remediated unless the change is low-risk for the local developer runtime, AWS cost posture, and portfolio evidence flow.

The following findings are accepted for now:

| Finding group | Current decision | Rationale | Safer future path |
|---|---|---|---|
| `CKV_K8S_43` image digest pinning | Accepted for local manifests | The current Kubernetes path uses local portfolio images such as `retailops-api:0.1.0` and `retailops-frontend:0.1.0`. Digest pinning is meaningful only after images are published to a registry and release tags are immutable. | Add registry-backed image publishing, generate SBOM/provenance, then pin deployed release images by digest. |
| `CKV_K8S_15` `imagePullPolicy: Always` | Accepted for local manifests | `IfNotPresent` supports local `kind` or `minikube` validation with locally built images. Changing to `Always` can break demos when images are not pushed to a remote registry. | Use `Always` only in a registry-backed cloud overlay or release overlay. |
| `CKV_K8S_40` high UID enforcement | Accepted for third-party local images | Official images such as PostgreSQL, Redpanda, and Nginx have image-specific user and filesystem assumptions. Forcing arbitrary UIDs can break startup or volume permissions. | Validate per-image non-root behavior in a separate hardening sprint before enforcing UIDs globally. |
| `CKV_K8S_22` read-only root filesystem | Accepted for stateful/helper workloads | PostgreSQL, Redpanda, migration jobs, and seed jobs may require writable paths beyond mounted data directories. Enforcing read-only root filesystems without runtime testing can break local smoke tests. | Add explicit writable `emptyDir` mounts per workload, then enable read-only root filesystems workload by workload. |
| `CKV_K8S_35` secrets as files | Accepted for current application contract | The API, jobs, and local Kubernetes overlay currently consume runtime configuration through environment variables. Moving secrets to mounted files requires application/config changes, not only manifest changes. | Introduce file-based secret loading or External Secrets integration in a dedicated runtime configuration change. |
| `CKV_AWS_338` CloudWatch log retention of at least one year | Accepted for dev-cost posture | The EKS module is portfolio/dev oriented. A 365-day default can increase CloudWatch Logs cost for temporary validation clusters. Short retention is intentional until there is a real production environment. | Use longer retention in a production overlay or make retention environment-specific. |
| `CKV_AWS_37` all EKS control plane log types | Accepted unless cloud evidence requires it | Additional EKS control plane logs improve auditability but can increase ingestion cost. The module already enables baseline control-plane logging; full logging should be chosen intentionally before real AWS apply. | Enable all EKS log types in a production/security showcase overlay when cost is understood. |
| `CKV_GHA_7` workflow dispatch inputs | Accepted for operator convenience | Manual workflow inputs are used for controlled portfolio validation, such as selecting a data profile or deciding whether to run an optional Terraform plan. Removing them reduces demo/operator ergonomics. | Keep inputs for non-release evidence workflows, or split release workflows into input-free variants later. |
| OpenAPI auth/security findings | Accepted until auth is implemented | The OpenAPI snapshot should reflect the real API. Adding fake security schemes only to satisfy a scanner would make the documentation less honest. | Add real authentication/authorization first, then regenerate the OpenAPI snapshot with security schemes. |
| Generated report secret findings | Accepted as scanner noise | Some findings come from generated Compose evidence under `ci-cd/reports`, where local demo values such as `retailops` appear in rendered output. These are not production secrets. | Sanitize generated evidence before publishing, or exclude generated report directories from source secret scans. |

Safe Kubernetes hardening that does not change runtime behavior may still be applied, such as explicit namespaces, disabling service account token mounts where Kubernetes API access is not needed, and dropping Linux capabilities for containers that do not require them.

## Future Hardening

- Promote dependency audits to blocking checks for high and critical findings.
- Add SBOM generation and image signing for release images.
- Add cloud secret storage through AWS Secrets Manager or SSM Parameter Store when a cloud runtime is implemented.
- Add a threat model and accepted-risk register.
- Add runtime detection only when there is a real deployed workload to monitor.
