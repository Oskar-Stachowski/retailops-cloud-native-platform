# RetailOps SBOM implementation

This folder contains the project SBOM configuration used for local evidence and
release-readiness documentation.

## Implemented controls

| Control | Implementation |
|---|---|
| Image SBOM | `syft <image> -o spdx-json` and `syft <image> -o cyclonedx-json` |
| Repository SBOM | `make sbom-repository` using `syft dir:.` |
| Repository evidence | `ci-cd/reports/sbom/retailops-repository-sbom-*-snapshot.*` |
| Provenance workflow | `.github/workflows/provenance-ci.yml` attests local API/frontend image subjects |
| Signed release SBOM attestation | Future registry-backed release step; do not claim until verified |

## Local commands

```bash
mkdir -p ci-cd/reports/sbom

make sbom-repository SBOM_SOURCE_VERSION=$(git rev-parse --short=12 HEAD)
```

The target writes:

```text
ci-cd/reports/sbom/retailops-repository-sbom-spdx-snapshot.json
ci-cd/reports/sbom/retailops-repository-sbom-cyclonedx-snapshot.json
ci-cd/reports/sbom/retailops-repository-sbom-summary-snapshot.txt
```

## Evidence rule

Safe current claim:

> Repository SBOM generation is implemented and captured with Syft in SPDX and
> CycloneDX formats.

Do not claim signed release SBOM attestations until a registry-backed release
image exists and the attestation/verification output is archived.
