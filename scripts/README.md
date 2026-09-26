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
