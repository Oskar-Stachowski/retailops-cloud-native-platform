# Terraform remote state and migration

The supported dev backend design is a dedicated S3 bucket in `eu-central-1`,
versioning, SSE-KMS, disabled ACLs, full public-access blocking and TLS-only
access. `use_lockfile = true` enables S3 native locking. HashiCorp now deprecates
DynamoDB-based locking; see the [S3 backend reference](https://developer.hashicorp.com/terraform/language/backend/s3).
CI pins Terraform 1.15.1; the state path requires at least 1.10.

## Current deployment boundary

The September 2026 audit found no active local state or matching state bucket on
the account used by RetailOps GitHub Actions. A historical saved plan contains
an empty state; it is not an authoritative current state or a migration source.
The persistent backend in `infra/state-backend` is prepared and tested with a
mock provider, but has not been applied. There is no AWS state migration to claim.
The account's remaining RetailOps GitHub plan role is outside the empty dev state.

## Ownership and access

- Owner: the RetailOps repository owner; region `eu-central-1`, workspace `default`.
- State key: `retailops/dev/terraform.tfstate`. Other environments need separate
  state/access design; do not reuse this key for them.
- Bootstrap bucket/KMS live in `infra/state-backend`, separate from temporary
  application infrastructure. `prevent_destroy` protects both from routine plans.
- A plan role can read state and bucket controls and write/delete **only the
  exact `.tflock` object**. A separate operator can also write state. Neither
  role needs permission to delete state versions.
- Account IDs, backend JSON, `.tfbackend`, `.tfvars`, state backups and plans
  stay out of Git. Credentials come from the AWS credential chain, never backend
  arguments or committed files.

The existing GitHub role is trusted only from this repository's `main` and uses
AWS `ReadOnlyAccess`. It was retained by this review. The bootstrap outputs
scoped backend policies; attaching lock permissions is part of backend
activation, not a change made by a plan run.

## First activation

1. Confirm the explicit target account and inventory existing resources/state.
   Recover a missing authoritative state before planning an existing deployment;
   do not substitute an empty baseline for recovery.
2. Plan `infra/state-backend` with private `bucket_name` and
   `expected_account_id` inputs. Review bucket/KMS ownership, ongoing costs,
   access-log/replication/notification exceptions and the bootstrap-state backup.
3. Provision the selected persistent backend as its own operation. Keep its
   state and recovery copy separately protected; application cleanup excludes it.
4. Read back versioning, encryption, ownership, public-access block, bucket
   policy and IAM scopes. Configure the exact account and state key.
5. For an existing local state, follow migration below. For a genuinely new
   deployment with no state, initialize the approved backend for the first apply;
   there is no old state to migrate.
6. Only after a state with managed resources exists, configure
   `TF_BACKEND_CONFIG_JSON` in GitHub and run the `drift` mode. A missing object,
   access denial or empty managed state must fail instead of reporting no drift.

## Migrating a real local state

Stop concurrent writers and use the operator identity, not the plan-only role.
Run from the actual initialized deployment checkout and preserve its private
variable inputs. Never migrate the historical `tfplan` retained in this project.

1. With `umask 077`, save `terraform state pull` outside the repo and record its
   checksum, lineage, serial and resource count without printing values.
2. Confirm the destination key is unused, or compare an existing destination
   state before proceeding. Do not overwrite a different lineage or newer state.
3. Copy `infra/environments/dev/backend.tf.example` to the ignored `backend.tf`.
   Fill an ignored `backend.s3.tfbackend` from its example, with the exact account,
   bucket and KMS ARN. Include `encrypt = true` and `use_lockfile = true`.
4. Run:

   ```bash
   terraform -chdir=infra/environments/dev init -migrate-state \
     -backend-config=backend.s3.tfbackend
   ```

   Review the migration prompt. `-reconfigure` does not copy state; do not use it
   as a substitute. Do not use `-force-copy` to bypass a destination conflict.
5. Pull state again and compare lineage, managed resource identities and values
   with the backup. Run normal and refresh-only plans using the same inputs.
6. Confirm the saved object has a version ID and expected KMS key. Exercise two
   concurrent plans in a controlled window to prove actual lock exclusion;
   check that the lock disappears after completion. No such live S3 drill has
   yet been recorded for this repository.

The [Terraform init reference](https://developer.hashicorp.com/terraform/cli/commands/init)
describes the distinct migration and reconfiguration modes.

## Recovery and cleanup

Keep the pre-migration backup until remote readback, plans and locking checks
pass. Versioning retains previous state versions; operators should retrieve a
specific version into a private file, inspect lineage/serial and resource
identities, and review a recovery plan before replacing current state. Restoring
state alone does not restore deleted infrastructure.

Do not disable locking, blindly force-unlock or run `terraform refresh` to make
a plan pass. Inspect the lock owner and running operations first. Do not destroy
the backend during an application showcase cleanup. KMS loss or an inaccessible
key can make every state version unreadable, so key recovery is part of state
recovery. Replication across regions is not configured by this dev bootstrap.
