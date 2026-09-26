# Terraform state and drift review — 2026-09-26

Step 5 audited the current RetailOps account and implemented a guarded,
repeatable plan workflow. The current result is **baseline only, no managed
state found**, not a claim that an existing deployment has no drift.
The S3/KMS backend is prepared and tested as configuration; cloud activation
and a real S3 migration/lock/recovery exercise remain pending.

## Current AWS and local state

The authenticated account was cross-checked against the existing repository
variable `AWS_TERRAFORM_PLAN_ROLE_ARN`. The corresponding role is
`retailops-dev-github-actions-terraform-plan`, with AWS `ReadOnlyAccess`, no
inline policies, and a trust condition for this repository's `main` branch.
The audit preserved this role and its permissions. An explicit matching
`AWS_TERRAFORM_ACCOUNT_ID` was configured for the workflow's account guard.

All 11 inventory reads completed: no matching RetailOps Project-tagged
resources, VPCs, ECR repositories, customer-managed IAM policies, application or
VPC flow-log groups, budgets, KMS aliases or candidate state buckets were found.
One matching IAM role remains as described above. Four unrelated bucket names
were listed but their objects were not read or changed. Discovery covers
`eu-central-1` plus account-wide IAM/S3 metadata; it is not an all-region cost
audit and does not rule out differently named or untagged resources/state.

There is no active local Terraform state in the project. The ignored historical
`infra/environments/dev/tfplan` contains an empty state and was inspected only
for metadata. It was not applied, treated as authoritative state or migrated.
Historical cleanup evidence retains its original date and scope.

The clean local plan on `e729ee82e72d0934b77c2a632297d92fa02fec04` proposed
**29 creates, 0 updates and 0 deletes**. The plan runner reported
`baseline_only_no_state`; Terraform's detailed exit code was 2 and the runner's
exit was 0 because this is the explicitly selected baseline mode. No cloud
resource was created, changed or deleted.

The final OIDC workflow from merged main `beae2b19abf6a39edb0bc2155baa85a0a887a3d4`
also passed both jobs with a clean checkout and the same 29-create baseline.
Its exact source, account guard, harness hash and removal of private temporary
artifacts were verified from the downloaded report. The plan step itself took
about 15 seconds, excluding setup and the preceding validation job.

## Implemented controls and actual tests

- An isolated configuration copy pins the AWS account and region. Raw plans,
  state values and output values stay out of CI artifacts and Git.
- Drift mode requires an existing nonempty managed S3 state. It verifies bucket
  ownership, versioning, SSE-KMS, private access, disabled ACLs, TLS policy and
  object encryption/version before initializing with native S3 locking.
- Normal and refresh-only plans distinguish external drift from configuration
  changes. A missing/denied/empty state, partial plan or failed assertion is an
  error. State contents are compared before/after review.
- The separate persistent bootstrap has a protected versioned bucket and
  rotating KMS key, explicit key policy and scoped state/lock IAM documents.
  No role attachment or cloud apply is automated.
- Required CI runs 12 regression tests, two mock-provider backend tests and a
  real Terraform local-file drill. The latter verified baseline, no changes,
  an out-of-band file change, a configuration change, local state migration,
  unchanged state after plans and cleanup.
- CI Checkov passed 117 checks with zero failures and three documented,
  resource-local dev exceptions (access-log delivery, regional replication and
  notifications). TFLint, format/validation, 16 CI path tests, actionlint,
  secret scans and the required application/runtime gates also passed.

The first CI attempt caught missing Linux native provider hashes and reliance
on an implicit KMS key policy. Both were fixed before merge. Provider packages
and checksums were fetched through Terraform and verified as signed by HashiCorp
for Linux AMD64 and macOS ARM64; provider versions were not changed.

## Traceable evidence

- [Implementation PR #47](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/pull/47).
- [Final Required CI run](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/actions/runs/36243524269).
- [Main-branch OIDC baseline workflow](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/actions/runs/36244078945).
- [Curated machine-readable results](2026-09-26-state-drift.json).
- [Drift runbook](../../runbooks/terraform-drift-check.md) and
  [remote-state activation/migration](../../runbooks/terraform-remote-state.md).

PR head `3266c80ef96868644697fcf6c0090bd6e9285e99` was tested through GitHub
merge `4b86566c68f26654dfa44acf9e59a6cc1c4bae82`. Its Git tree
`79fd4bb2d2a8b2bc38aef703a58ee6e917fe60b4` exactly matches merged main
`beae2b19abf6a39edb0bc2155baa85a0a887a3d4`.

The curated JSON retains source and script hashes, inventory scope/counts,
local/OIDC baseline results, CI contract-drill results and verified artifact
checksums. Raw Terraform plans, state, credentials and account IDs are excluded.
The downloaded validation ZIP matched SHA-256
`e2d624eada6b6abf92075b739919c1eb06a8d8838c8a589d9f3ce5d6d525d21f`,
and the OIDC plan ZIP matched
`76b515f25da47d3adc3d921e2ad12892f384b55f9d3e0ed85f1ad149b8e4a468`.
GitHub artifacts have limited retention; this summary remains in the repository.

## Limits and remaining cloud work

No active deployment/state means there was no real cloud state to migrate or
refresh for drift. Successful baseline planning is not a live drift result.
The integration migration/drift test uses `local_file`; the backend controls use
a mock AWS provider. They do not establish S3 lock collision handling, live state
version recovery or successful AWS backend migration.

Before the next managed cloud deployment, activate the reviewed persistent
backend, protect its own bootstrap state, attach scoped lock access, configure
the exact backend and deployment inputs, and capture live locking/recovery
evidence. The existing read-only role alone cannot acquire an S3 lock. No
scheduled drift job is enabled while no managed state exists. EKS and RetailOps
AI remain separate work.
