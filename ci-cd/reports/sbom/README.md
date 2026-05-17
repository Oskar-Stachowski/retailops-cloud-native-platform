# SBOM evidence

Generated SBOM files belong here. Repository-level snapshots are intentionally
small enough to commit and are named with `*-snapshot.*` so they fit the
repository evidence policy.

Current repository evidence:

```text
retailops-repository-sbom-spdx-snapshot.json
retailops-repository-sbom-cyclonedx-snapshot.json
retailops-repository-sbom-summary-snapshot.txt
```

Refresh command:

```bash
make sbom-repository SBOM_SOURCE_VERSION=$(git rev-parse --short=12 HEAD)
```

Future registry-backed image examples:

```text
retailops-api.spdx.json
retailops-api.cyclonedx.json
retailops-frontend.spdx.json
retailops-frontend.cyclonedx.json
```
