# RetailOps Terraform IAM OIDC Module for EKS IRSA

**Scope:** EKS issuer provider and trust-policy helper; not wired into dev.
This module is separate from the GitHub Actions OIDC provider and plan role.

## Purpose

This module introduces the IAM OpenID Connect provider foundation used by EKS IAM Roles for Service Accounts, commonly called IRSA.

Its responsibilities are:

- create an IAM OIDC provider for the EKS cluster issuer URL,
- expose the OIDC provider ARN for workload IAM role trust policies,
- expose IRSA condition keys for `aud` and `sub`,
- optionally generate an example assume-role policy for selected service accounts,
- keep IAM roles and Kubernetes service accounts outside this module.

IRSA is important because pods should not inherit broad node-level AWS permissions. A pod that needs S3, DynamoDB, SQS, CloudWatch, Secrets Manager, or another AWS API should receive only the exact IAM role it needs through its Kubernetes service account.

## What this module creates

When used by an environment and applied intentionally, this module can create:

- one `aws_iam_openid_connect_provider` for an existing EKS cluster OIDC issuer URL.

The module also produces optional helper output:

- `irsa_assume_role_policy_json` when `irsa_service_accounts` are provided.

This helper is a generated trust-policy document. It does not create workload IAM roles.

## What this module does not create

The following are outside this module:

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

The environment must supply and validate them separately.

## Design decisions

| Area | Decision |
|---|---|
| Identity model | Use IAM OIDC provider as the foundation for IRSA. |
| Module boundary | OIDC provider only; workload IAM roles are not created here. |
| Input source | `cluster_oidc_issuer_url` is injected from the EKS module output. |
| Audience | Defaults to `sts.amazonaws.com`, required for standard IRSA. |
| Thumbprints | Defaults to an empty list with provider `>= 5.100.0`; explicit thumbprints can be passed if required. |
| Service accounts | Optional input only for generating trust-policy JSON. |
| Subject matching | Exact `system:serviceaccount:<namespace>:<name>` subjects, no wildcard by default. |
| Tags | Project, environment, lifecycle, module, and cost context are applied. |
| Apply policy | Requires an existing cluster issuer and the [AWS activation plan](../../plans/aws-activation.md). |

## Example environment wiring

The caller must first wire EKS and tags; this is not present in the current dev root.

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

  tags = module.tags.common_tags
}
```

Later, a workload IAM role can use:

```hcl
assume_role_policy = module.iam_oidc.irsa_assume_role_policy_json
```

For a real production-style setup, prefer one IAM role per distinct permission set rather than one broad role shared by many service accounts.

## Output contract

Outputs:

| Output | Why it matters |
|---|---|
| `oidc_provider_arn` | Used as the federated principal in IAM role trust policies. |
| `oidc_provider_url` | Evidence that the IAM provider matches the EKS issuer URL. |
| `oidc_provider_host_path` | Required prefix for IRSA trust policy condition keys. |
| `irsa_audience_condition_key` | Used to require token audience `sts.amazonaws.com`. |
| `irsa_subject_condition_key` | Used to restrict which service account can assume a role. |
| `irsa_service_account_subjects` | Shows selected service account identities. |
| `irsa_assume_role_policy_json` | Optional role trust-policy helper. |
| `service_account_role_annotation_key` | Documents the service-account role annotation. |

## Plan-first validation commands

Run from the repository root:

```bash
terraform fmt -recursive infra/modules/iam_oidc
terraform -chdir=infra/modules/iam_oidc init -backend=false
terraform -chdir=infra/modules/iam_oidc validate
```

After deployment, verify that the IAM provider URL equals the deployed EKS
issuer, audience is `sts.amazonaws.com`, and trust subjects match exact
namespace/service-account pairs. Creating the provider alone does not grant AWS
access to any Pod. Validate the selected workload role and service-account
annotation with its intended permissions. See the
[AWS activation plan](../../plans/aws-activation.md).
