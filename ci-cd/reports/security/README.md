# Security Report Snapshots

This directory contains security scanner outputs that are useful as evidence.

Most raw security reports remain ignored because they can be large, volatile, or contain environment-specific metadata. Tracked files should be sanitized snapshots and should be linked from `docs/evidence/index.md`.

## Tracked Files

| File | What it proves | Risk note |
|---|---|---|
| `trivy-fs-snapshot.txt` | Filesystem/dependency scan was executed and showed 0 vulnerabilities for the captured dependencies. | Snapshot can become stale as vulnerability databases change. |
| `trivy-api-image-snapshot.txt` | API image scan was executed and showed no vulnerabilities in the captured snapshot. | Snapshot can become stale as base image advisories change. |
| `trivy-frontend-image-snapshot.txt` | Frontend image scan was executed and found critical vulnerabilities. | Keep as internal evidence until the base image is remediated and a clean replacement snapshot is collected. |

## Ignored Local Outputs

Raw files such as `gitleaks.json`, `trivy-fs.txt`, `trivy-api-image.txt`, and `trivy-frontend-image.txt` are ignored unless converted into sanitized `*-snapshot.*` evidence.
