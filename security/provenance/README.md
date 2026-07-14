# RetailOps provenance implementation

RetailOps uses GitHub artifact attestations for build provenance of local API
and frontend image subjects.

## Implemented workflow

`.github/workflows/provenance-ci.yml` uses
`actions/attest-build-provenance@v2` for:

- API image provenance attestation;
- frontend image provenance attestation;
- a Markdown provenance summary uploaded as a workflow artifact.

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
  --repo Oskar-Stachowski/retailops-cloud-native-platform \
  <subject-digest-or-artifact>
```

For a registry-backed release, verify immutable image digests after the release
workflow publishes them. Do not claim production release provenance from the
local workflow alone.

## Evidence

The provenance CI workflow writes:

```text
ci-cd/reports/provenance/provenance-summary.md
```

The curated local evidence boundary is documented in:

```text
ci-cd/reports/provenance/provenance-ci.evidence.md
docs/evidence/security/sbom-provenance-evidence.md
```
