# RetailOps image signing implementation

RetailOps uses Sigstore Cosign for OCI image signing.

## Implemented release path

The workflow `.github/workflows/ecr-release.yml`:

1. authenticates to AWS with GitHub OIDC;
2. builds API and frontend images;
3. pushes images to AWS ECR;
4. generates Trivy scan reports;
5. generates SPDX and CycloneDX SBOMs with Syft;
6. signs pushed image digests with Cosign keyless signing;
7. verifies the signatures;
8. generates GitHub provenance and SBOM attestations;
9. uploads release evidence.

## Required GitHub configuration

Set these repository secrets/variables before running the workflow:

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

## Evidence

Expected files after a successful ECR release:

```text
ci-cd/reports/signing/cosign-api-verify.txt
ci-cd/reports/signing/cosign-frontend-verify.txt
ci-cd/reports/sbom/retailops-api.spdx.json
ci-cd/reports/sbom/retailops-frontend.spdx.json
ci-cd/reports/provenance/ecr-release-summary.md
```
