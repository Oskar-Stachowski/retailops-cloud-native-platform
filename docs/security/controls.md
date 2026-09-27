# Security

This document describes the controls configured under `security/`, `policy/` and `.github/workflows/`.

## Related instructions

- [SBOM and provenance](sbom.md)
- [Static analysis](sast.md)
- [Kubernetes policies](kubernetes-policies.md)
- [External Secrets candidate](external-secrets.md)
- [Falco rule candidates](falco.md)
- [Demo identity boundary](demo-auth-boundary.md)

## Implemented Controls

| Area | Implementation |
|---|---|
| Secret scanning | Gitleaks configuration and GitHub Actions workflow |
| Filesystem and image vulnerability scanning | Trivy local targets and Security CI jobs |
| Python dependency audit | `pip-audit` evidence in Security CI |
| Frontend dependency audit | `npm audit` evidence in Security CI |
| Terraform linting | TFLint configuration for IaC quality gates |
| Terraform policy scanning | Blocking Checkov gate with documented exceptions |
| Kubernetes policy scanning | Kubeconform, Conftest and blocking Checkov baseline |
| Critical IaC guardrails | Makefile and CI checks for IAM users, access keys, AdministratorAccess, and wildcard IAM actions |
| Repository SBOM | Syft-based `make sbom-repository` target with SPDX, CycloneDX and text snapshots |
| Build provenance | Local-image provenance workflow plus signed registry-release manifests, image provenance and SPDX SBOM verification before release promotion |

## Current Policy

Required CI uses explicit blocking thresholds:

- Gitleaks blocks findings outside the narrow, explicit allowances in `.gitleaks.toml`.
- Trivy filesystem scanning blocks fixed `HIGH` and `CRITICAL` findings.
- Trivy image scanning blocks fixed `CRITICAL` findings.
- Security CI and the Compose `security-tools` container both pin Trivy `0.74.0`; Docker CI verifies the container starts and records its version.
- `pip-audit` blocks any vulnerability reported for runtime and development Python dependencies.
- `npm audit --include=dev --audit-level=high` blocks high or critical findings in both production and development dependencies, including the frontend build toolchain.
- Bandit blocks high-severity, high-confidence backend findings.
- TFLint is a blocking IaC quality gate.
- Checkov blocks every Terraform or Kubernetes finding except the check IDs explicitly accepted below.
- Conftest denies mutable `latest` tags, incomplete resources/probes, privilege escalation and committed runtime Secret manifests.

## Accepted IaC Exception

`CKV_AWS_356` is skipped in `security/iac/checkov.yml` for the Terraform plan read-only discovery policy. The policy intentionally uses wildcard resources only for AWS `Get`, `List`, and `Describe` actions required by Terraform plan. It does not grant create, update, delete, pass-role, or administrator permissions. The Makefile guardrails still block wildcard IAM actions and privileged policy patterns.

## Accepted Checkov Findings

The unactivated `infra/state-backend` dev bootstrap has three resource-local
exceptions: S3 access-log delivery (`CKV_AWS_18`), cross-region replication
(`CKV_AWS_144`) and event notifications (`CKV2_AWS_62`). No destination/consumer
is provisioned for these. Versioning, KMS encryption, TLS-only access and public
access blocking remain mandatory. The [bootstrap notes](../reference/terraform-state-backend.md)
record the production review boundary; no repository-wide skips are added.

Checkov is a hard gate. Only the listed check IDs are excluded from the blocking baseline; scanner failures and every other finding fail Required CI.

The following findings are accepted for now:

| Finding group | Current decision | Rationale | Safer future path |
|---|---|---|---|
| `CKV_K8S_43` image digest pinning | Accepted for local manifests | The current Kubernetes path uses local portfolio images such as `retailops-api:0.2.1` and `retailops-frontend:0.2.1`. The verified GHCR release is separate from the native local Kubernetes build path. | Connect a release overlay to verified registry digests and validate admission/runtime there. |
| `CKV_K8S_15` `imagePullPolicy: Always` | Accepted for local manifests | `IfNotPresent` supports local `kind` or `minikube` validation with locally built images. Changing to `Always` can break demos when images are not pushed to a remote registry. | Use `Always` only in a registry-backed cloud overlay or release overlay. |
| `CKV_K8S_40` high UID enforcement | Accepted for third-party local images | Official images such as PostgreSQL, Redpanda, and Nginx have image-specific user and filesystem assumptions. Forcing arbitrary UIDs can break startup or volume permissions. | Validate per-image non-root behavior in a separate hardening sprint before enforcing UIDs globally. |
| `CKV_K8S_23` root-container admission | Accepted for the same third-party local workloads | This check is globally skipped for the dev manifest set, which includes vendor/helper workloads and pod-level security contexts. PostgreSQL already has a verified non-root UID 70; the skip does not imply that every workload runs as root. Conftest still blocks privileged mode and privilege escalation. | Verify each image, then set explicit non-root users and remove this exception. |
| `CKV_K8S_22` read-only root filesystem | Accepted for stateful/helper workloads | PostgreSQL, Redpanda, migration jobs, and seed jobs may require writable paths beyond mounted data directories. Enforcing read-only root filesystems without runtime testing can break local smoke tests. | Add explicit writable `emptyDir` mounts per workload, then enable read-only root filesystems workload by workload. |
| `CKV_K8S_35` secrets as files | Accepted for current application contract | The API, jobs, and local Kubernetes overlay currently consume runtime configuration through environment variables. Moving secrets to mounted files requires application/config changes, not only manifest changes. | Introduce file-based secret loading or External Secrets integration in a dedicated runtime configuration change. |
| `CKV_AWS_338` CloudWatch log retention of at least one year | Accepted for dev-cost posture | The EKS module is portfolio/dev oriented. A 365-day default can increase CloudWatch Logs cost for temporary validation clusters. Short retention is intentional until there is a real production environment. | Use longer retention in a production overlay or make retention environment-specific. |
| `CKV_AWS_37` all EKS control plane log types | Accepted unless cloud evidence requires it | Additional EKS control plane logs improve auditability but can increase ingestion cost. The module already enables baseline control-plane logging; full logging should be chosen intentionally before real AWS apply. | Enable all EKS log types in a production/security showcase overlay when cost is understood. |

The YAML `skip-check` lists apply to their whole configured scan, not only to the workloads named in the rationale. Inspect `security/k8s/checkov.yml` and `security/iac/checkov.yml` for the exact scope. Resource-local state-backend exceptions are documented above.

## Future Hardening

- Remove accepted Checkov exceptions as registry-backed images and hardened workload filesystems become available.
- Extend verified release-image attestations to deployment admission when a deployment runtime exists.
- Add cloud secret storage through AWS Secrets Manager or SSM Parameter Store when a cloud runtime is implemented.
- Add a threat model and accepted-risk register.
- Exercise the existing Falco rule candidates when runtime detection is selected; rule files alone do not prove a deployed detector.
