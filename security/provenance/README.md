# RetailOps provenance implementation

RetailOps uses GitHub artifact attestations for build provenance and SBOM attestations.

## Implemented workflow

`.github/workflows/ecr-release.yml` uses `actions/attest@v4` for:

- image provenance attestation;
- SPDX SBOM attestation;
- pushing attestations to the container registry.

## Required workflow permissions

```yaml
permissions:
  contents: read
  id-token: write
  attestations: write
```

## Verify provenance

```bash
gh attestation verify \
  "oci://<account-id>.dkr.ecr.eu-central-1.amazonaws.com/retailops-dev-api:<tag>" \
  -R Oskar-Stachowski/retailops-cloud-native-platform
```

## Evidence

The release workflow writes:

```text
ci-cd/reports/provenance/ecr-release-summary.md
```
