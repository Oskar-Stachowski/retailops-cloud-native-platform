# RetailOps Terraform IAM OIDC Module for EKS IRSA

**Commit:** 13.4 — `terraform: add IAM OIDC foundation for EKS`

**Sprint:** 13 — Kubernetes / EKS Foundation

**Status:** Module skeleton, plan-first, no IAM workload roles or Kubernetes service accounts created yet.

## Purpose

This module introduces the IAM OpenID Connect provider foundation required for future EKS IAM Roles for Service Accounts, commonly called IRSA.

The goal of Commit 13.4 is to make the security boundary explicit before workloads are deployed:

- create an IAM OIDC provider for the EKS cluster issuer URL,
- expose the OIDC provider ARN for future IAM role trust policies,
- expose IRSA condition keys for `aud` and `sub`,
- optionally generate an example assume-role policy for future service accounts,
- keep IAM roles and Kubernetes service accounts out of scope until later commits.

Senior DevOps note: IRSA is important because pods should not inherit broad node-level AWS permissions. A pod that needs S3, DynamoDB, SQS, CloudWatch, Secrets Manager, or another AWS API should receive only the exact IAM role it needs through its Kubernetes service account.

## What this module creates

When used by an environment and applied intentionally, this module can create:

- one `aws_iam_openid_connect_provider` for an existing EKS cluster OIDC issuer URL.

The module also produces optional helper output:

- `irsa_assume_role_policy_json` when `irsa_service_accounts` are provided.

This helper policy is evidence and a future building block. It does not create workload IAM roles.

## What this module does not create

The following items are intentionally out of scope for Commit 13.4:

- EKS cluster control plane,
- EKS managed node groups,
- IAM roles for application pods,
- IAM policies for application pods,
- Kubernetes namespaces,
- Kubernetes service accounts,
- Helm releases,
- workload manifests,
- EKS Pod Identity associations,
- production RBAC model.

Those belong to later Sprint 13 commits or later production-readiness work.

## Design decisions

| Area | Decision |
|---|---|
| Identity model | Use IAM OIDC provider as the foundation for future IRSA. |
| Module boundary | OIDC provider only; workload IAM roles are not created here. |
| Input source | `cluster_oidc_issuer_url` is injected from the EKS module output. |
| Audience | Defaults to `sts.amazonaws.com`, required for standard IRSA. |
| Thumbprints | Defaults to an empty list with provider `>= 5.100.0`; explicit thumbprints can be passed if required. |
| Service accounts | Optional input only for generating future trust-policy evidence. |
| Subject matching | Exact `system:serviceaccount:<namespace>:<name>` subjects, no wildcard by default. |
| Tags | Project, environment, lifecycle, module, and cost context are applied. |
| Apply policy | Do not apply in this commit unless the EKS cluster already exists and an explicit validation window is planned. |

## Example usage for a later environment commit

Do not wire this into `infra/environments/dev` in Commit 13.4 unless that is your explicit task.

```hcl
module "iam_oidc" {
  source = "../../modules/iam_oidc"

  project_name            = "retailops"
  environment             = "dev"
  cluster_name            = module.eks.cluster_name
  cluster_oidc_issuer_url = module.eks.cluster_oidc_issuer_url

  irsa_service_accounts = [
    {
      namespace = "retailops-app"
      name      = "retailops-api"
    },
    {
      namespace = "retailops-platform"
      name      = "retailops-worker"
    },
    {
      namespace = "retailops-observability"
      name      = "metrics-reader"
    }
  ]

  tags = local.common_tags
}
```

Later, a workload IAM role can use:

```hcl
assume_role_policy = module.iam_oidc.irsa_assume_role_policy_json
```

For a real production-style setup, prefer one IAM role per distinct permission set rather than one broad role shared by many service accounts.

## Output contract

Important outputs for later commits:

| Output | Why it matters |
|---|---|
| `oidc_provider_arn` | Used as the federated principal in IAM role trust policies. |
| `oidc_provider_url` | Evidence that the IAM provider matches the EKS issuer URL. |
| `oidc_provider_host_path` | Required prefix for IRSA trust policy condition keys. |
| `irsa_audience_condition_key` | Used to require token audience `sts.amazonaws.com`. |
| `irsa_subject_condition_key` | Used to restrict which service account can assume a role. |
| `irsa_service_account_subjects` | Shows prepared future service account identities. |
| `irsa_assume_role_policy_json` | Optional future role trust-policy helper. |
| `service_account_role_annotation_key` | Documents the Kubernetes annotation used later. |

## Plan-first validation commands

Run from the repository root:

```bash
terraform fmt -recursive infra/modules/iam_oidc
terraform -chdir=infra/modules/iam_oidc init -backend=false
terraform -chdir=infra/modules/iam_oidc validate
```

Recommended evidence capture:

```bash
mkdir -p ci-cd/reports/iac
terraform -chdir=infra/modules/iam_oidc validate \
  | tee ci-cd/reports/iac/terraform-validate-iam-oidc-module.txt
```

When the module is later wired into `infra/environments/dev`, generate a plan only:

```bash
terraform -chdir=infra/environments/dev plan \
  -out=tfplan-iam-oidc

terraform -chdir=infra/environments/dev show -no-color tfplan-iam-oidc \
  | tee ci-cd/reports/iac/terraform-plan-iam-oidc.txt
```

Do not run `terraform apply` as part of Commit 13.4 unless the EKS cluster already exists and the validation/cleanup procedure is documented.

## Verification after a real apply

After a controlled apply, useful read-only checks are:

```bash
aws eks describe-cluster \
  --name retailops-dev-eks \
  --query "cluster.identity.oidc.issuer" \
  --output text

aws iam list-open-id-connect-providers

terraform -chdir=infra/environments/dev output iam_oidc_provider_arn
```

The OIDC provider URL in IAM must match the EKS cluster issuer URL.

## Senior review checklist

Before moving to Commit 13.5 or Commit 13.6, verify:

- the module creates only `aws_iam_openid_connect_provider`,
- the OIDC issuer URL comes from the EKS module output or environment wiring,
- `oidc_provider_arn` is exposed as an output,
- `sts.amazonaws.com` is included in `client_id_list`,
- no broad workload IAM role is created in this commit,
- no Kubernetes service account is created in this commit,
- future service account subjects are exact and namespace-scoped,
- tags include project, environment, module, lifecycle, and cost context,
- there is no `terraform apply` evidence unless this was an intentional EKS validation window,
- `terraform fmt` and `terraform validate` pass locally.

## Common mistakes

| Mistake | Why it is risky |
|---|---|
| Creating one broad IAM role for all pods | Breaks least privilege and makes incidents harder to contain. |
| Trusting all service accounts in a namespace with a wildcard too early | Convenient, but too permissive for a portfolio-grade security story. |
| Forgetting the `aud` condition | A token with the wrong audience could be accepted by the trust policy. |
| Hardcoding an issuer URL manually | Easy to mismatch the real EKS cluster issuer. Prefer module output wiring. |
| Treating IRSA as a container security boundary | IRSA scopes AWS permissions, but containers and pods still need runtime hardening. |
| Applying before cluster creation | The OIDC issuer URL exists only after a real EKS cluster is created. |
