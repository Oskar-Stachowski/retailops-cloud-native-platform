# Fundament repozytorium AI — pierwszy zakres etapu 01

Data: **2026-09-27**. Pierwszy zakres etapu 01; cały etap pozostaje
`in_progress`. Źródło planu i poprzedniego audytu w RetailOps: `8a9e620`.

## Repo i wersje

Repo lokalne: `/Users/oskarstachowski/retailops-ai-intelligence`,
obok RetailOps, branch `ai/implementation`. Nie ma skonfigurowanego remote
ani publikacji na GitHub.

| Commit w repo AI | Zakres |
|---|---|
| `e03d7df5200f75526a2e7c711bf502ddce97dd9a` | Repo, MIT, ADR-y i zasady, pakiet/settings/CLI, kontrakt metadanych, lockfile, testy i workflow Required CI. |
| `5da5fdc04e8e44510a489c0f0cc45557cf87e15d` | Dowody odtworzenia na czystym checkout, prób blokad i instalacji wheel. |

Pełne komendy, wyniki, sumy artefaktów i ograniczenia są w repo AI:
`docs/evidence/01-foundation.md` oraz `docs/evidence/01-foundation.json`.
Bieżącą instrukcję uruchomienia zawiera tam `docs/development.md`, a aktualne
możliwości `docs/STATUS.md`. Ten wpis wskazuje dowody między repozytoriami.

## Weryfikacja lokalna

- macOS ARM64, Python **3.11.15**, uv **0.12.19**, instalacja z `uv.lock`.
- Świeży clone i nowe środowisko, `uv sync --locked` z uprzednio pobranego cache,
  następnie `make ci-local`: **22 testy**, Ruff/format, Mypy strict, dokumentacja,
  build wheel/sdist oraz skany Gitleaks historii i katalogu.
- Kontrolowane błędy kontraktu, zmiana zależności bez aktualizacji lockfile
  oraz syntetyczny nieaktywny token dawały exit 1 odpowiedniej kontroli.
  Pliki po próbach przywrócono; checkout pozostał czysty.
- Wheel zainstalowany w osobnym środowisku runtime: CLI/import poza checkoutem
  korzystały z site-packages, `uv pip check` potwierdziło zgodność zależności.
- Actionlint zweryfikował workflow. Actions są przypięte do pełnych SHA;
  testy bramek obejmują pominięcia, ignorowanie błędów i filtry ścieżek.
- Po instalacji w docelowym katalogu ponowne `make check`: **22 passed in 1.90s**,
  pozostałe kontrole bez błędów; CLI `config-check --env-file .env.example`
  potwierdziło poprawną konfigurację. Repo pozostało czyste.

Nie uruchomiono GitHub Actions ani ochrony gałęzi. Nie jest to odbiór HTTP,
PostgreSQL/MLflow, modeli, brokera ani AWS. Następny zakres i pozostałe kryteria:
[backlog](../../../plans/ai/backlog.md).
