# SBOM And Provenance Evidence

Capture date: 2026-05-17  
Branch: `devops-platform-readiness`  
Source commit: `38cab9839f2c`  
Tool: Syft 1.44.0  
Validation command:

```bash
make sbom-repository SBOM_SOURCE_VERSION=38cab9839f2c
```

## Generated SBOM Artifacts

| Artifact | Format | What it proves | Size |
|---|---|---|---:|
| `ci-cd/reports/sbom/retailops-repository-sbom-spdx-snapshot.json` | SPDX JSON | Repository dependency and workflow/action inventory can be exported in SPDX format. | ~252 KB |
| `ci-cd/reports/sbom/retailops-repository-sbom-cyclonedx-snapshot.json` | CycloneDX JSON | The same repository inventory can be exported in CycloneDX format for scanner/tool compatibility. | ~180 KB |
| `ci-cd/reports/sbom/retailops-repository-sbom-summary-snapshot.txt` | Syft table | Human-readable dependency summary for quick reviewer inspection. | ~3.7 KB |

Quick validation summary:

| Check | Result |
|---|---:|
| SPDX packages | 76 |
| SPDX files | 21 |
| SPDX relationships | 158 |
| CycloneDX components | 96 |
| CycloneDX dependencies | 4 |

The snapshot intentionally excludes volatile local folders such as `.git`,
`.terraform`, `node_modules`, virtual environments, caches, `dist`, `build` and
coverage output through `security/sbom/syft.yaml`.

## Provenance Boundary

Implemented:

- `.github/workflows/provenance-ci.yml` builds local API and frontend images.
- The workflow captures local image digests.
- The workflow calls `actions/attest-build-provenance@v2` for both image
  subjects.
- The workflow uploads `ci-cd/reports/provenance/provenance-summary.md` as CI
  evidence.

Not claimed from this local evidence:

- A fresh GitHub Actions provenance run was not executed in this local task.
- No ECR image was pushed.
- No release image signature was verified with Cosign.
- No SBOM attestation for a registry-published image was verified.

Safe recruiter/video wording:

> The project includes reproducible Syft SBOM generation and a GitHub Actions
> provenance workflow for local image subjects. Signed release verification is
> documented as the next registry-backed release step and is not overclaimed.

Unsafe wording to avoid:

> All production images are signed and verified.

That claim requires immutable registry image digests and captured `cosign verify`
output.
