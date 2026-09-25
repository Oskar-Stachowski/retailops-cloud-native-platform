# Security Evidence

Last reviewed: 2026-09-25. Existing SBOM snapshots retain their original date.

This folder stores curated, reviewer-facing security evidence. Raw scanner and
SBOM outputs stay under `ci-cd/reports/` and are linked here only when they are
small, sanitized and useful during portfolio review.

| File | What it proves | Related area | Validation note |
|---|---|---|---|
| [2026-09-25 CI validation](../github-actions/2026-09-25-validation.md) | Dependency audits, Gitleaks, Trivy, TFLint and Checkov passed their documented gates. | Current scanning evidence | Includes exact PR revisions, job links, artifact retention and scan boundaries. |
| `sbom-provenance-evidence.md` | Repository SBOM snapshots were generated with Syft and the provenance/signing claim boundary is explicit. | SBOM, supply chain, provenance | Captured from `make sbom-repository SBOM_SOURCE_VERSION=38cab9839f2c`. |

## Refresh Commands

```bash
make sbom-repository SBOM_SOURCE_VERSION=$(git rev-parse --short=12 HEAD)
```

After refreshing, update `docs/evidence/index.md` and this README if the
artifact names, counts or claim boundary changed.
