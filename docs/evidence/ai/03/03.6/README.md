# AI 03.6 — odbiór danych między repozytoriami

**Odebrany 29.09.2026 lokalnie i na Linux CI, na osobnych opublikowanych
branchach/PR-ach. Można rozpocząć AI 04 oraz równolegle AI 06.**

Generator → reports/przeliczona kwalifikacja → eksport → typed CSV/Parquet
parity → niezależny import → curated → pełna weryfikacja → as-of przechodzi
na obu standardowych smoke dwukrotnie. Osobny kontrolowany przypadek późnej
sprzedaży również przechodzi dwukrotnie. Nie wykonano treningu ani odbioru modelu.

[Wyniki i lineage](verification.json) zawierają effective config, watermarks,
wersje i fingerprints kodu/locków, wszystkie counts/grains/ranges/logiczne hashe,
SHA schematów oraz references/checksums każdego manifestu.
[Karta danych](dataset-card.md) określa zakres użycia;
[runbook](../../../../reference/ai03-cross-repo.md) podaje odtworzenie.

## Przypięte rewizje i publikacja

- RetailOps: `25fb0b887503c119055af86b63991299465096b9`, branch
  `ai/03-01-parquet`, [PR #65](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/pull/65).
- Importer/curated: `cb053cc29c1906d79108cba2c70f88b56e454211`, branch
  `ai/03-04-importer`, [PR #5](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/pull/5).
  Opublikowany head `7dd00cce51497d8cd7b90615309b3e9b67b6e513` dodaje wyłącznie
  dokumentację do tej rewizji; wykonywany kod i fingerprints są identyczne.
- Linux PR checkout: `9d75f9f8a114f2baa3923fd15cb6b03b94431b8c`, syntetyczny
  merge GitHub dla RetailOps head `25fb0b8`. Raport zapisuje rzeczywisty SHA,
  z którym działał generator i exporter, a metadane CI wiążą go z head PR.
- Source 2.6.0; snapshot/handoff/curated 1.0.0; canonical source 1.6.0,
  curated 1.0.0. Python 3.11.15, PyArrow 25.0.1, uv 0.12.19.

Oba checkouty były czyste i przypięte przed każdym przebiegiem i po nim.
Consumer używa własnego interpretera, bez generatora i operacyjnej DB RetailOps.
Prace AI 12 pozostały w odrębnym worktree. Publikacja brancha/PR i zaliczenie
Required CI nie oznaczają merge na main; nie wykonano takiego merge.

## Pomiary pełnej ścieżki

Każda komórka obejmuje dwa przebiegi od nowej generacji. Wiersze oznaczają
pełne 25 tabel facts/plans, zachowane również w curated.

| Przypadek | Wiersze | Darwin ARM64: czas / max RSS | Linux AMD64: czas / max RSS |
|---|---:|---:|---:|
| `ai-smoke`, 30 dni / 20 produktów | 31 171 | 102,04–169,52 s / 141,53 MiB | 51,48–52,37 s / 204,06 MiB |
| `ai-temporal-smoke`, 102 dni / 8 produktów | 52 973 | 180,23–203,48 s / 173,81 MiB | 90,60–90,67 s / 259,09 MiB |
| `controlled-late-fact`, 8 dni / 2 produkty | 609 | 8,03–8,06 s / 99,61 MiB | 3,48–3,51 s / 141,11 MiB |

Seed 42, koniec historii 2026-07-31. Standardowych profili nie zmniejszono.
Wszystkie przebiegi spełniły **300 s / 1024 MiB na pojedynczy pipeline**.
Pomiar obejmuje uruchomienie dwóch kolejnych świeżych workerów, wszystkie
weryfikacje i as-of; instalacja zależności jest poza pomiarem. RSS jest
konserwatywną sumą szczytu orkiestratora i większego szczytu workera;
workery nie nakładają się. Lokalny host nie był dedykowanym benchmark runnerem.

Dodatkowe re-export/reimport/rebuild pozostają obowiązkowymi, osobno mierzonymi
kontrolami idempotencji. Required Data CI wykonuje generator/export/verify/
reexport na obu pełnych profilach dwukrotnie. Required CI AI wykonuje domyślne
fixture snapshot-import-check i curated-check z reimport/rebuild dwukrotnie.
Nie doliczamy dodatkowych przejść do czasu jednego normalnego pipeline.

Source/snapshot/curated IDs i wszystkie typed logiczne tabele są identyczne
w obu powtórzeniach oraz między Darwin i Linux. `generated_at` i lokalna ścieżka
nie zmieniają identity. Każda kwalifikacja przechodzi **46 hard gates**;
quarantine = 0, evaluation truth w curated = false, input pozostaje niezmienny.

## Późny fakt i wymagane kontrole

Standardowe profile dla seeda 42 nie mają quantity revisions. Osobny fixture
opóźnia ingestion jednej rzeczywistej wygenerowanej sprzedaży do zamknięcia
dnia + 1 godzina, odtwarza zależne obserwacje/historię i przechodzi ponownie
rzeczywiste bramki źródła. To przypadek odbioru, nie standardowy profil ani
dane przeznaczone do treningu. Dokładna mutacja, config i SHA skryptu są w JSON.

Obserwacja `d5580d1c-2952-570f-9119-282b5b1c796d` otrzymuje version 2 dostępną
`2026-07-25T01:00:00+00:00`. Mikrosekundę wcześniej reader zwraca starszą wersję;
w chwili dostępności nową. Cały wynik as-of, klucze, version, observed_units
i observation_status są porównywane z niezależnym wyborem z raw source history.

Importer zachowuje zakresy dat z licznikiem zero dla pustych tabel i kolumn
z samymi null. Cztery regresje sprawdzają poprawne i zmienione zakresy;
metadane nadal są przeliczane z typed Parquet.
Pozostałe wymagane testy obejmują corruption/missing/unsafe paths, unsupported
versions, fałszywe IDs i konflikty treści, failed source gates, partycje i grain,
truth isolation, missing/ambiguous mapping, gap vs zero/closed, future versions,
immutable publication, concurrency, przerwanie/SIGKILL i retry/cleanup.

## Required CI i przechowywanie dowodów

[RetailOps Required CI](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/actions/runs/36540743369)
ma **25/25 success**, w tym **89 testów danych w 196,36 s**, oba profile z
re-exportem, pełna bramka cross-repo, API, frontend, Docker, kind/persistence/
rollback, security i IaC.
[AI Required CI PR](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/actions/runs/36541696909)
oraz [push brancha AI](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/actions/runs/36541692890)
mają success. PR obejmuje **747 testów w 405,85 s**, bez failures/skips,
Ruff/format, strict mypy (117 plików), docs/kontrakty, handoff, import/curated,
wheel/sdist, Compose config oraz rzeczywisty Compose/persistence.
Wymagany job cross-repo propaguje failure do `required-result`; nie ignoruje błędów.

Pełny lokalny raport i 18 manifestów pozostają poza Git w
`ci-cd/reports/data/ai03-cross-repo.json` i `ci-cd/reports/data/ai03-cross-repo/`.
[Artefakt Linux](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/actions/runs/36540743369/artifacts/11020906556)
ma 19 plików: pełny raport + 18 manifestów. Zweryfikowano każdy byte SHA/rozmiar
oraz SHA256 ZIP `2e0be76f14d827007145ce394386354e72b0a538091a0291f6764a758cdbe687`.
GitHub przechowuje go do 13.10.2026; identyczny ZIP zachowano lokalnie pod
`ci-cd/reports/data/ai03-cross-repo-linux-36540743369.zip`.
Mały rejestr w Git zachowuje wyniki i checksums po wygaśnięciu artefaktu;
duże CSV/Parquet są tymczasowe i nie trafiają do Git.

Polecenia wykonania: [commands.md](commands.md). Piny i skrypty pozwalają
ponowić odbiór. Generator nadal materializuje źródło; smoke nie jest odbiorem
pełnych ai-dev/ai-training ani modelu. Inventory false, model/anomaly/stockout/
replay mają dalsze bramki. Po 06/07 użyj nowych niezmiennych IDs i ponów zależne oceny.
