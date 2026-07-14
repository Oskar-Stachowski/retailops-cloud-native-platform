# RetailOps image signing policy

RetailOps documents a Sigstore Cosign policy for future registry-backed OCI
image signing. No signed release image is claimed until immutable image digests
exist and `cosign verify` output is captured.

## Intended release path

The future registry-backed release path should:

1. authenticates to AWS with GitHub OIDC;
2. builds API and frontend images;
3. pushes images to AWS ECR;
4. generates Trivy scan reports;
5. generates SPDX and CycloneDX SBOMs with Syft;
6. signs pushed image digests with Cosign keyless signing;
7. verifies the signatures;
8. generates GitHub provenance and SBOM attestations;
9. uploads release evidence.

Current implemented adjacent controls:

- repository SBOM snapshots are generated with `make sbom-repository`;
- `.github/workflows/provenance-ci.yml` generates GitHub build provenance
  attestations for local image subjects;
- Cosign identity verification policy is documented in
  `security/signing/cosign-identity-policy.md`.

## Required GitHub configuration

Set these repository secrets/variables before adding or running a
registry-backed release workflow:

| Name | Type | Example |
|---|---|---|
| `AWS_ROLE_TO_ASSUME` | secret | `arn:aws:iam::<account-id>:role/retailops-dev-iam-github-actions-ecr-release-role` |
| `AWS_REGION` | variable | `eu-central-1` |
| `ECR_API_REPOSITORY` | variable | `retailops-dev-api` |
| `ECR_FRONTEND_REPOSITORY` | variable | `retailops-dev-frontend` |

## Verify signatures

```bash
cosign verify \
  --certificate-identity-regexp "https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/.github/workflows/ecr-release.yml@.*" \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com" \
  <account-id>.dkr.ecr.eu-central-1.amazonaws.com/retailops-dev-api@sha256:<digest>
```

## Evidence boundary

Expected files after a future successful signed release:

```text
ci-cd/reports/signing/cosign-api-verify.txt
ci-cd/reports/signing/cosign-frontend-verify.txt
ci-cd/reports/sbom/retailops-api.spdx.json
ci-cd/reports/sbom/retailops-frontend.spdx.json
ci-cd/reports/provenance/ecr-release-summary.md
```

Safe current claim:

> Cosign signing policy is documented; repository SBOM and local-image
> provenance evidence exist.

Do not claim:

> RetailOps release images are already signed and verified.
