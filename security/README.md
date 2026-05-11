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

## Future Hardening

- Promote dependency audits to blocking checks for high and critical findings.
- Add SBOM generation and image signing for release images.
- Add cloud secret storage through AWS Secrets Manager or SSM Parameter Store when a cloud runtime is implemented.
- Add a threat model and accepted-risk register.
- Add runtime detection only when there is a real deployed workload to monitor.
