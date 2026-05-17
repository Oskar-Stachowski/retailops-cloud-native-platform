# Provenance reports

Runtime provenance summaries from GitHub Actions are uploaded as workflow artifacts. Do not commit generated attestation bundles or large image artifacts to Git.

Current curated boundary:

```text
provenance-ci.evidence.md
```

Expected workflow artifact after `.github/workflows/provenance-ci.yml` runs:

```text
provenance-summary.md
```
