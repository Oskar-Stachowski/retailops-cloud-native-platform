# Kubernetes Reports

Local Kubernetes smoke and manifest validation reports are written here.

Raw reports are ignored by default because they are environment-specific and
regenerated locally or in CI. Track only curated `*-snapshot.txt` files or short
evidence notes after reviewing them for local paths, private hostnames and other
environment-specific details.

## Current Tracked Snapshots

| Path | Purpose |
|---|---|
| `kubernetes-smoke-snapshot.txt` | Render, parse and kubeconform validation for base/dev Kustomize manifests plus probe/resource checks. |
| `kubernetes-secret-scan-snapshot.txt` | Gitleaks scan of Kubernetes manifests and secret examples. |
