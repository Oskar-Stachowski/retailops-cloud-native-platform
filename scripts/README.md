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
