# Pełna bramka danych RetailOps → AI

`scripts/data/verify_ai03_cross_repo.py` wykonuje generator → reports i ponowną
kwalifikację → snapshot → import → curated. Wymaga dwóch czystych checkoutów
oraz pełnych Git SHA obu repo. Konsument działa we własnym interpreterze;
nie kopiuje generatora, nie czyta operacyjnej bazy RetailOps i nie używa AWS.

## Uruchomienie

Zainstaluj zależności przed pomiarem: w RetailOps `make data-parquet-install`,
a w osobnym checkoutcie AI `uv sync --locked --extra snapshot`.
Wskaż czysty worktree AI 03, niezależny od prac nad AI 12:

```sh
AI03_CONSUMER_ROOT=/absolute/path/to/clean-ai03-worktree
AI03_PRODUCER_REVISION="$(git rev-parse HEAD)"
AI03_CONSUMER_REVISION="$(git -C "$AI03_CONSUMER_ROOT" rev-parse HEAD)"
services/api/.venv/bin/python scripts/data/verify_ai03_cross_repo.py \
  --consumer-root "$AI03_CONSUMER_ROOT" \
  --consumer-python "$AI03_CONSUMER_ROOT/.venv/bin/python" \
  --producer-revision "$AI03_PRODUCER_REVISION" \
  --consumer-revision "$AI03_CONSUMER_REVISION"
```

Każdy profil `ai-smoke` i `ai-temporal-smoke` jest generowany od początku
dwukrotnie: seed 42, koniec 2026-07-31, standardowe rozmiary. Każdy pełny
przebieg ma limit **300 s / 1024 MiB**, z uruchomieniem procesów, kwalifikacją, weryfikacją i odczytem as-of,
bez instalowania zależności. Każdy pomiar obejmuje jeden normalny pipeline.
Workery działają kolejno;
pamięć jest konserwatywną sumą szczytu orkiestratora i większego szczytu workera.
Warunek budżetu lub integralności kończy polecenie błędem i raportem `failed`.

Bramka porównuje typy, wartości, grain, counts, zakresy i logiczne hashe
25 tabel CSV/Parquet; oba powtórzenia muszą zachować source/snapshot/curated IDs.
Dodatkowe re-export/reimport/rebuild są kontrolami idempotencji, mierzonymi
osobno: wymagany producer benchmark oba pełne profile dwukrotnie oraz
wymagane consumer snapshot-import-check/curated-check. Pozostają obowiązkowe
w Required CI i muszą zachować opublikowane bajty. Nie doliczamy drugiego
eksportu/importu/buildu do opóźnienia pojedynczego pipeline.
Odczyt as-of jest porównywany z niezależnym wyborem wersji z raw source.

## Osobny przypadek późnego faktu

Domyślne smoke dla seeda 42 nie mają quantity revisions. Dodatkowy
`controlled-late-fact` ma jawne parametry `ai-smoke`, 8 dni, 2 produkty,
seed 42, koniec 2026-07-31. Opóźnia ingestion jednej rzeczywistej wygenerowanej
sprzedaży do zamknięcia dnia + 1 godzina i odtwarza zależne obserwacje/historię.
To kontrolowany fixture odbioru, nie standardowy benchmark ani zmiana generatora.
Kod konstrukcji fixture jest przypięty przez SHA skryptu i commit RetailOps.

Następnie rzeczywiste bramki źródła, exporter, importer, curated i reader
wykonują pełną ścieżkę dwukrotnie. Wszystkie 46 hard gates muszą przejść.
Origin mikrosekundę przed korektą widzi poprzednią ilość; w chwili dostępności
widzi nową. Przypadek ma własne source/curated IDs i raport z dokładną mutacją.

## Wyniki i CI

Raport: `ci-cd/reports/data/ai03-cross-repo.json`. Pełne manifesty i ich byte SHA:
`ci-cd/reports/data/ai03-cross-repo/<profile>/<repeat>/`. Duże CSV/Parquet są
prywatnymi plikami tymczasowymi pod generated i nie trafiają do Git.
Raport zachowuje wersje kodu/locków, config, watermarks, counts, schemas,
checksums, as-of, readiness i zasoby; pełne manifesty można sprawdzić bez datasetu.

Required Data CI uruchamia tę samą bramkę z przypiętym consumer SHA w
`.github/workflows/data-ci.yml`, Python 3.11.15, uv 0.12.19 i locked dependencies.
Job jest wymagany: failure propaguje przez `data-gate` do `required-result`.
Repo AI ma własny Required CI, pełne testy i rzeczywisty Compose/persistence.
Zmiana zachowania konsumenta wymaga jawnej aktualizacji pinu i ponownego odbioru.

[Końcowe evidence AI 03.6](../evidence/ai/03/03.6/README.md) zawiera odbiór
cross-repo oraz publikację na main obu repo z Required CI. Forecast source jest ready,
inventory pozostaje false; model, anomaly, stockout i replay mają dalsze bramki.
Po ledgerze 06 i scenariuszach 07 wykonaj tę ścieżkę na nowych IDs i ponów
zależne oceny. Zachowaj niezmienność wcześniejszych snapshotów.
