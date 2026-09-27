# SBOM i pochodzenie artefaktów

Repozytorium obsługuje dwa zakresy zestawienia zależności:

| Zakres | Implementacja |
|---|---|
| Pliki repozytorium | `make sbom-repository`, Syft, SPDX i CycloneDX |
| Dokładne obrazy wydania | Workflow release, Trivy SPDX, podpisane attestations oraz weryfikacja obrazu po digest |

```bash
make sbom-repository
```

Raporty powstają w `ci-cd/reports/sbom/` i pozostają lokalnymi artefaktami.
SBOM repozytorium nie zastępuje SBOM konkretnego obrazu kontenera.

Podpisywanie, tożsamość workflow i sprawdzenie zawartości SBOM przed publikacją
opisuje [polityka wydań](../governance/releases.md). Instrukcja wykonania:
[release do GHCR](../runbooks/registry-release.md). Ostatni utrwalony wynik:
[wydanie v0.2.1](../evidence/releases/2026-09-26-registry.md).

Osobny `.github/workflows/provenance-ci.yml` dotyczy lokalnych obrazów CI;
nie jest dowodem opublikowania obrazu do rejestru.
