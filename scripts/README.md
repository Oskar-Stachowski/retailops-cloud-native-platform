# Scripts

This directory contains helper scripts for local development, testing, build
automation, and deployment support.

Planned MVP / target responsibilities:
- support local environment setup,
- run tests and validation checks,
- build Docker images,
- support local deployment or demo workflows,
- provide repeatable developer commands.

Current CI helpers include Docker Compose smoke checks, streaming and
observability checks, and a Kubernetes smoke test that renders and validates the
local Kustomize manifests.

`make k8s-runtime-drill` uses `scripts/kubernetes/drill.py` to create and remove
an isolated kind cluster, test ingress/policies/streaming, and verify persistent
data through restart, update and rollback. See the
[runbook](../docs/runbooks/local-kubernetes-runbook.md).

`scripts/terraform/inventory.py` reads the selected RetailOps account inventory.
`make terraform-plan-dev` produces an isolated empty-state baseline;
`make terraform-drift` reviews existing S3 state with account/backend guards.
Both need `TF_EXPECTED_ACCOUNT_ID`. `make terraform-state-test` tests backend
controls and real local-file drift/migration without AWS credentials. See the
[drift runbook](../docs/runbooks/terraform-drift-check.md).
