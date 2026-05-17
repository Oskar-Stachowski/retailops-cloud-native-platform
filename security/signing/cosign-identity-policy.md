# Cosign identity verification policy

Use keyless signing for GitHub Actions releases.

Allowed issuer:

```text
https://token.actions.githubusercontent.com
```

Allowed identity pattern:

```text
https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/.github/workflows/ecr-release.yml@.*
```

Verification command:

```bash
cosign verify \
  --certificate-identity-regexp "https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/.github/workflows/ecr-release.yml@.*" \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com" \
  "$IMAGE_BY_DIGEST"
```

Operational rule:

- sign only immutable image digests;
- do not sign mutable `latest` tags;
- archive verification output as CI evidence.
