# Terraform baseline and drift review

Use `make terraform-plan-dev` for an explicitly empty-state baseline and
`make terraform-drift` only when an existing S3 state manages real resources.
Both commands run in a private temporary copy, preserve the working checkout,
keep locking enabled and never apply a plan. The report contains counts and
classifications, not raw attributes, outputs, account IDs or resource identifiers.

## Prerequisites and commands

Use Terraform 1.10 or newer (CI pins 1.15.1), AWS CLI and Python 3.11+.
Set the expected account explicitly from the reviewed account configuration:

```bash
export AWS_PROFILE=YOUR_RETAILOPS_PROFILE
export TF_EXPECTED_ACCOUNT_ID=YOUR_REVIEWED_ACCOUNT_ID
python3 scripts/terraform/inventory.py
make terraform-plan-dev
```

The inventory reads tagged/named RetailOps foundation resources in eu-central-1
and account-wide IAM/S3 metadata. It records failures as unverified, not zero,
and leaves existing roles/resources untouched. It is not an all-region cost audit.

The profile must authenticate to that exact account. The provider and, for drift,
the backend also enforce the account. Environment-injected Terraform CLI flags,
logging and variable overrides are removed to keep the operation predictable.
Only tracked Terraform configuration and the dev example inputs are copied.
The runner currently supports the dev example configuration; different deployment
inputs require extending this contract before using the runner for that deployment.

For existing remote state, create ignored
`infra/environments/dev/backend.config.json` from its `.example` file:

```bash
make terraform-drift
```

The backend check requires the exact dev key, versioning, KMS encryption,
public-access block, disabled ACLs, a TLS-only bucket policy and an existing
KMS-encrypted state object. Missing/denied state and zero managed resources fail.
S3 state locking requires scoped lock-file writes even for a read-only
infrastructure plan. See [backend access and migration](terraform-remote-state.md).

## What the result means

| Classification | Meaning | Runner exit |
|---|---|---:|
| `baseline_only_no_state` | Plan from an intentionally empty state; not evidence of an existing deployment or no drift. | 0 |
| `no_drift` | Existing managed state checked; no external, configuration or output changes detected. | 0 |
| `drift_detected` | Real objects differ from stored state, observed in normal or refresh-only plan JSON. | 2 |
| `configuration_or_output_changes` | Changes require review, but the plan has no detected external resource drift. | 2 |
| failed report | Account/backend/authentication/provider error, empty remote state, incomplete plan or failed check. | 1 |

Terraform's own `-detailed-exitcode` reports 0 for no changes, 2 for changes and 1
for an error. A code of 2 alone does not distinguish drift from code changes.
The runner inspects `resource_drift` separately from `resource_changes`, runs both
normal and refresh-only plans for existing state, and checks that the state was
not modified during the review. It rejects partial/deferred plans and failing
check assertions. See [plan semantics](https://developer.hashicorp.com/terraform/cli/commands/plan)
and the [JSON format](https://developer.hashicorp.com/terraform/internals/json-format).

Reports are `ci-cd/reports/terraform-state/<run>/report.json`. Temporary plans and
raw output are not published. Inspect failures in a private operator session;
do not paste raw state or `terraform show -json` into CI artifacts. A detected
change is a review result, never a command to run apply automatically.

## CI and proof

`make terraform-state-test` runs regression checks, mock-provider backend-control
tests and an actual local-file Terraform drill. The drill creates a disposable
file, migrates its local state, modifies the file outside Terraform, then changes
configuration. It verifies distinct results and unchanged state after plans,
and removes all temporary files. This proves the classifier with real Terraform;
it does not prove a live AWS S3 migration or lock collision.

Required CI runs these checks without AWS credentials. The separate manual
`Terraform State and Drift Review` workflow is restricted to `main`, uses the
existing OIDC role and an explicit `AWS_TERRAFORM_ACCOUNT_ID` repository variable.
Choose `baseline` or, after backend activation, `drift`. The latter additionally
requires `TF_BACKEND_CONFIG_JSON`. Only sanitized JSON reports are uploaded.
There is no scheduled AWS job while no managed deployment/state exists.

For errors, check account selection, credentials, the exact state location and
provider diagnostics privately. A plan against an empty state does not establish
that AWS is empty: inventory and state ownership must be reviewed separately.
