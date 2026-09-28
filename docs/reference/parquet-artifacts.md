# Parquet i polityka artefaktów — AI 03.1

Wersja formatu `retailops-parquet-1.0.0`. Konwerter przyjmuje rozdzielone
źródło AI **2.6.0** i zachowuje source ID oraz kanoniczne hashe wszystkich
40 tabel. Jest warstwą zapisu plików: `status=format_only`,
`snapshot_ready=false`. Publikacja niezmiennego snapshotu z bramkami use case
jest dostępna przez [eksporter 03.2](ai-snapshots.md); importer i curated
pozostają dalszymi zakresami 03.

## Zależności i uruchomienie

[Grupa Parquet](../../data/requirements-parquet.txt) przypina PyArrow 25.0.1.
Instaluje ją `make data-parquet-install`. API, seed CSV i izolowany worker
nie wymagają Arrow. Implementacja korzysta z jawnego schema i zapisu/odczytu
porcjami opisanego w [dokumentacji Apache Arrow](https://arrow.apache.org/docs/python/parquet.html).

Z katalogu głównego projektu:

```bash
make data-parquet-install
services/api/.venv/bin/python -m data.generator.main \
  --profile ai-smoke --seed 42 --end-date 2026-07-31 \
  --output-dir data/generated/ai03/example-csv
services/api/.venv/bin/python -m data.export.parquet \
  --source-dir data/generated/ai03/example-csv \
  --output-dir data/generated/ai03/example-parquet
```

Wybierz nowy katalog dla następnego przebiegu. Konwerter odmawia nadpisania
istniejącego katalogu. Weryfikuje kompletność descriptor/artifacts, source ID,
kolumny, klasy, checksumy i rozmiary CSV, liczby oraz logiczne hashe, a następnie
odczytuje każdy zapisany Parquet i porównuje typed content. Kopiuje raporty po
kontroli checksumów. Nie przelicza źródłowych quality gates; do kwalifikowanej
publikacji użyj [eksportera snapshotów](ai-snapshots.md).
Przerwany zapis może zostawić niekompletny katalog; nie dostaje finalnego
`manifests/format.json` i nie jest gotowym snapshotem.

## Typy, zapis i layout

Jawny schema obejmuje `int64`, `bool`, `date32`, `timestamp[us, UTC]`, tekst NFC,
kwoty `decimal128(38,2)` oraz współczynniki `decimal256(76,40)`. Nie używa float
dla pieniędzy i nie zaokrągla danych przy zmianie formatu. Nullability zachowuje
brak pomiaru, otwarte okresy i puste listy. Null, zero, closed i kolejne wersje
obserwacji pozostają różnymi wartościami. Nadmierna precyzja, NaN/inf,
niecałkowite counts, timestamp bez strefy lub z precyzją poniżej mikrosekundy
oraz niedozwolony null są odrzucane.

```text
data/generated/<run>/
  facts/<table>/[business_date=YYYY-MM-DD/]part-*.parquet
  truth/<table>/[business_date=YYYY-MM-DD/]part-*.parquet
  operational_outputs/<table>/part-*.parquet
  raw_events/
  reports/
  manifests/dataset_manifest.json
  manifests/dataset_manifest.v2.json
  manifests/format.json
```

`source_observation` i `source_plan` trafiają do facts, `simulation_truth` do
truth, a demonstracyjne forecasts/anomalies/workflow do operational_outputs.
`raw_events` jest puste: obecne źródło nie zawiera strumienia surowych injekcji.
Layout nie nadaje nowych uprawnień ani nie dołącza truth do cech.

Zapis ma domyślnie **8192 wiersze** na porcję, maksymalnie **65536**, dodatkowo
limit **8 MiB komórek CSV na porcję** i **64 KiB na rekord**. Row groups nie
przekraczają rozmiaru porcji. Kompresja: Zstandard. Dla tabel od **50000 wierszy**
partycja używa business_date lub dnia zdarzenia w UTC. Pozycje zamówień używają
daty orders.ordered_at przez bounded indeks SQLite; brak powiązania jest błędem.
Tabele bez daty są porcjowane bez wymyślania dat. Pojedynczy plik zachowuje
oryginalne kolumny dat; przy odczycie katalogów podaj zadeklarowany schema,
aby automatyczne rozpoznawanie Hive nie zmieniło typów.

Hash logiczny zachowuje istniejącą kanonizację **1.6.0** i multiset, w tym duplikaty.
Sort odbywa się na dysku w SQLite z cache 2 MiB. Podział na pliki i partycje
nie zmienia tego hasha. Format manifest podaje schema, grain, klasyfikację,
daty, counts oraz SHA-256/bytes/rows każdego pliku; writer ma hash kodu i grupy
zależności. Kopia source manifest zachowuje dotychczasową identity/provenance.

## Git, fixtures i cleanup

Git śledzi demo CSV, maksymalnie jeden bieżący fixture pod `data/fixtures/`
oraz archiwa regresji poprzednich source schemas. Łączny limit fixtures to
**5 MiB po rozpakowaniu**, także dla ZIP. Obecnie archiwa mają 2435356 B;
bieżący fixture cross-repo zostanie dodany w 03.3. `data/synthetic/`,
`data/generated/` i `data/replay/` są ignorowane. Eksport small wyłączono ze
śledzenia; lokalne pliki zostały zachowane. `api-seed-small` i `compose-seed`
generują brakujące seed CSV; kompletne istniejące CSV pozostają bez zmian,
a częściowy katalog wymaga jawnego przygotowania.

Cleanup przyjmuje wyłącznie katalog potomny root `data/generated` tego repo.
Chroni wszystkie śledzone pliki, także staged fixtures i nazwy ze znakami glob.
Odrzuca root, wyjście poza root, `..`, symlinki w ścieżce i w zawartości.
Domyślnie pokazuje liczbę plików i bytes; usunięcie wymaga flagi:

```bash
services/api/.venv/bin/python -m data.export.cleanup data/generated/ai03/example-parquet
services/api/.venv/bin/python -m data.export.cleanup data/generated/ai03/example-parquet --delete
```

## Weryfikacja i koszt

`make data-parquet-check` uruchamia testy formatu/polityki/snapshotu, kontrolę tracked
fixtures oraz oba pełne profile smoke dwukrotnie, w świeżych procesach.
Wymagana bramka Data CI wywołuje to samo polecenie i zapisuje JUnit oraz benchmark
pod `ci-cd/reports/data/`. Bieżąca polityka `ai03-snapshot-budget-1.0.0` ma limit
**300 s i 1024 MiB peak RSS na pełny przebieg profilu**. Obejmuje generację,
CSV, kwalifikację, eksport Parquet, odczyt kontrolny i niezmienny re-export;
instalacja zależności jest poza pomiarem. Format-only benchmark pozostaje
dostępny przez `python -m data.export.benchmark` bez flagi `--snapshot`.
Przekroczenie czasu/RSS albo zmiana identity przy powtórzeniu kończy się błędem.
Cały job Data CI ma timeout 30 minut, z zapasem na cztery przebiegi i instalację.

Opcjonalny benchmark dużego writera:

```bash
services/api/.venv/bin/python -m data.export.stress --rows 1460000 \
  --output ci-cd/reports/data/ai03-writer-scale.json
```

To kontrolowana tabela do pomiaru writera, **nie profil ai-training** ani źródło
kwalifikowane do ML. Duży zapis jest bounded; dotychczasowa generacja źródła
oraz source quality nadal budują tabele w pamięci. Pełnych ai-dev/ai-training
nie zmierzono i nie przyznaje się im odbioru end-to-end na podstawie tego testu.
[Evidence 03.1](../evidence/ai/03/03.1/README.md) podaje rzeczywiste wyniki lokalne.
