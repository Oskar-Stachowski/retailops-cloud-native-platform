# Provenance CI Evidence Boundary

Capture date: 2026-05-17  
Source commit reviewed: `38cab9839f2c`

## Implemented

`.github/workflows/provenance-ci.yml` provides a GitHub Actions provenance path
for the local image subjects:

- builds `retailops-api:provenance`;
- builds `retailops-frontend:provenance`;
- captures Docker image IDs as subject digests;
- generates `ci-cd/reports/provenance/provenance-summary.md`;
- attests API and frontend image subjects with
  `actions/attest-build-provenance@v2`;
- uploads `provenance-ci-evidence` as a workflow artifact.

## Required GitHub Permissions

```yaml
permissions:
  contents: read
  id-token: write
  attestations: write
```

## Claim Boundary

This file documents the implemented workflow and expected evidence artifact. It
is not a substitute for a fresh GitHub Actions run screenshot or attestation
verification output.

Safe claim:

> Provenance workflow is implemented and configured to generate GitHub artifact
> attestations for locally built API and frontend image subjects.

Do not claim:

> Release images are signed and provenance-verified in production.

That stronger claim requires a registry-backed release, immutable image digests,
and captured verification output.
