# Persistent Terraform state bootstrap

This is a separate, **not yet deployed** Terraform root for RetailOps dev state
in `eu-central-1`. It creates one private, versioned S3 bucket and a rotating KMS
key, with a 30-day key deletion window, TLS-only bucket access and disabled ACLs.
The bucket and key use `prevent_destroy`; the bucket does not allow force-emptying.
State versions do not expire automatically. Incomplete multipart uploads expire
after seven days.

It is separate from `infra/environments/dev` so application cleanup cannot
destroy the state store. S3 native locking requires Terraform 1.10 or newer;
CI pins 1.15.1. No DynamoDB lock table is required. The S3 service's Object Lock
feature is not the Terraform lock mechanism and is not enabled here.

Inputs are `bucket_name` (`retailops-...-tfstate`) and `expected_account_id`.
The provider rejects a different account. Keep real inputs in ignored private
`.tfvars` files. Use the committed provider lock file.

```bash
terraform -chdir=infra/state-backend init -backend=false -input=false -lockfile=readonly
terraform -chdir=infra/state-backend validate
terraform -chdir=infra/state-backend test
```

Tests use a mock AWS provider; they do not provision a bucket or prove live S3
locking/recovery. Before activation, review a real plan against the pinned
account, determine the bootstrap state's backup owner/location and account for
ongoing S3/KMS costs. This persistent root is not part of the temporary showcase
destroy procedure. No `apply` is automated by CI.

Outputs provide the exact backend settings and separate IAM policy documents:

- `plan_state_policy`: reads the exact state object; writes/deletes only its
  `.tflock`; permits KMS use through S3 and reads bucket security controls.
- `operator_state_policy`: additionally permits writing that state object for
  migration/apply. Neither policy permits deleting state or historical versions.

These documents are **not attached to any role automatically**. They supplement
resource discovery permissions. The current GitHub role has AWS `ReadOnlyAccess`;
it can run a baseline plan but cannot acquire an S3 state lock. Activate scoped
lock access only with the selected backend. GitHub trust must be restricted to
this repository's protected `main`, and human migration access kept separate.

Dev bootstrap exceptions are resource-local: access-log delivery (`CKV_AWS_18`),
cross-region replication (`CKV_AWS_144`) and bucket event notifications
(`CKV2_AWS_62`) have no configured destination/consumer. They do not disable
encryption, TLS, public-access or versioning checks. Choose monitoring and a
regional-disaster recovery target before a production deployment.

Follow the [state activation and migration runbook](../../docs/runbooks/terraform-remote-state.md).
