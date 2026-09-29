# Snapshot i curated inventory 1.1 — AI 06

[Końcowy odbiór](../evidence/ai/06/final/README.md) obejmuje exporter
w RetailOps i niezależny importer w repo AI. Wejściem są
[source 2.7](inventory-source-dataset.md) oraz
[qualification 1.0](inventory-label-qualification.md). Snapshot1.0/source 2.6
zachowuje osobne schemas i jawny tryb zgodności `--source-version 2.6`. Domyślne CLI AI generuje 2.7; demo/API i seeder zachowują wcześniejszy kontrakt.

## Najprostsza pełna ścieżka

W RetailOps, po `make data-parquet-install`:

```sh
services/api/.venv/bin/python -m data.export.ai_snapshot \
  --profile ai-smoke --seed 42 --end-date 2026-07-31 \
  --output-root data/generated/inventory-snapshots
```

Komenda generuje source 2.7, kwalifikuje prywatne okna i publikuje snapshot 1.1.
Zwrócone `path` i source ID są wejściem importu poniżej. Sam generator
`python -m data.generator.main --profile ai-smoke` publikuje źródło pod
`data/generated/sources/<source_id>`; `--output-dir` wybiera katalog nadrzędny.

## Eksport

Wymagane są Python/PyArrow z przypiętego środowiska API. Najpierw utwórz source
i qualification ich CLI; ID i directory znajdziesz w wygenerowanych receipts.
Z katalogu RetailOps wykonaj:

```sh
services/api/.venv/bin/python -m data.export.inventory_snapshot \
  --source-dir data/generated/inventory-sources/<source_id> \
  --dataset-id <source_id> \
  --qualification-dir data/generated/inventory-qualifications/<qualification_id> \
  --output-root data/generated/inventory-snapshots
```

`<source_id>` i `<qualification_id>` zastąp rzeczywistymi IDs z receipts.
Output musi być osobnym katalogiem pod `data/generated`; exporter odmawia
zapisu w tracked fixtures i poza tym rootem. Wynik CLI to `publication` oraz
`path`; kompletny manifest znajduje się w opublikowanym katalogu.

Eksporter sprawdza manifest i dokładną allowlistę wejścia, kopiuje wszystkie
58 tabel CSV i metadata do private staging, a następnie wykonuje
pełny `read_source_dataset` na tej kopii. Ponownie liczy 36 gates i realism,
sprawdza explicit ID oraz niezmienność manifestu podczas kopiowania.
Qualification kopiuje do osobnego staging i rekwalifikuje z już zweryfikowanych
tabel tej samej source copy. Nie pomija recomputation okien ani checksums;
unikamy powtórnego liczenia całych source gates na tej samej prywatnej kopii.

## Artefakty i lineage

Schema manifestu to1.1.0, policy `retailops-inventory-snapshot-1.0.0`,
format `retailops-parquet-1.1.0`. Wykonywalny kontrakt:
[inventory_snapshot.v1_1.schema.json](../../data/contracts/inventory_snapshot.v1_1.schema.json).
Source ID, qualification ID, ich descriptors, schema fingerprints i exporter
code/dependency hashes wiążą snapshot. Snapshot ID zależy od typed logical
content; chunking, physical checksums i execution timestamps nie zmieniają ID.

```text
inventory-snapshots/<source_id>/
  snapshot_manifest.json
  manifest.sha256
  facts/<table>/part-*.parquet                  # dokładnie43 tables
  evaluation_truth/<table>/part-*.parquet       #12 tables, tylko opt-in
  evaluation_truth/qualification/              #3 pliki, tylko opt-in
  schemas/                                    #reviewed JSON i Arrow
  reports/                                    #source/realism JSON+MD
  manifests/dataset_manifest.v2.json
```

43 facts/plans to 25 dotychczasowych commerce tables i 18 dodatkowych native
inventory tables. Wspólne `return_events` jest native. Nie publikujemy legacy
`price_history`, `promotions`, `returns`, users ani wyników modeli jako worker facts.
Money ma fixed scale2, quantities/versions są integer, flags boolean,
date/UTC microseconds i nullable fields zachowują typy. Native content hash
CSV jest odtwarzany z Parquetu; commerce zachowuje typed multiset identity.

`--include-evaluation-truth` dodaje12 private tables i trzy pliki kwalifikacji,
w tym `simulation_truth/inventory_qualified_windows.json`. Wariant ma inne
snapshot ID i wymaga osobnego output root, gdy facts wariant tego source już
istnieje. Wszystkie odczyty private wariantu wymagają explicit opt-in.
Qualification i private parameters/outcomes pozostają poza worker facts/cechami.

Przed atomową publikacją odczyt ponownie sprawdza bytes, schemas, grain,
typed content, parent projection, operational graph i known snapshots z ledgeru.
Wariant private sprawdza również pełną rekwalifikację okien i raportu.
Powtórny identyczny eksport zwraca `reused`; istniejący wariant nie jest naprawiany
ani nadpisywany. Pliki mają mode600, private directories700.

## Import w repo AI

Na branchu `ai/06-inventory-handoff`, po `uv sync --locked --extra snapshot`:

```sh
.venv/bin/python -m retailops_ai.source_snapshot.cli import \
  --snapshot-dir /path/to/RetailOps/data/generated/inventory-snapshots/<source_id> \
  --generated-root data/generated --require-use-case inventory_source
.venv/bin/python -m retailops_ai.source_snapshot.cli verify-import \
  --import-dir data/generated/snapshots/<source_id>
```

Dodaj `--allow-evaluation-truth` do importu i każdego późniejszego odczytu
private wariantu. Importer nie korzysta z producer imports ani bazy RetailOps.
Weryfikuje reviewed contracts, producer gate receipt, typed/source hashes,
ledger/opening/sign/chronology, known snapshots, historyczny routing i issues,
commerce quantity/revenue, refund/restock oraz supply orders/plans/receipts.
Nie regeneruje prywatnego popytu, całych36 gates ani pełnej kwalifikacji labeli.
Sprawdza qualification schema/lineage/checksums i report aggregates.

## Curated i historyczny odczyt w repo AI

```sh
.venv/bin/python -m retailops_ai.curated.cli build \
  --import-dir data/generated/snapshots/<source_id> --generated-root data/generated
.venv/bin/python -m retailops_ai.curated.cli as-of \
  --curated-dir data/generated/curated/<curated_id> \
  --origin 2026-07-31T23:59:59.999999+00:00 --table inventory_daily_snapshots
```

Curated zachowuje 43 facts/plans i fizyczny grain product × stock × business date.
Sales używa availability native sale; return oryginalnego magazynu, snapshot
własnego cutoff. Plany dostaw są wybierane według wersji znanej w origin,
rzeczywiste receipts dopiero po dostępności. Bez informacji o czasie rekord
pozostaje `not_recorded`, a brak historycznego stanu nie jest zerem ani
fallbackiem do przyszłego snapshotu. Private import wymaga opt-in także przy
build; żadne truth table lub label nie wchodzi do curated.

Czytnik `CuratedReader` weryfikuje zbiór raz i przechowuje jego manifest prywatnie.
Każde zapytanie sprawdza hash/count/grain odczytywanej tabeli przed zwróceniem
wyniku. Podmiana plików po walidacji nie zmienia zaakceptowanego widoku.
Curated ma nowy ID i `inventory_ready=true` wyłącznie bez odrzuconych rekordów.
Modelowe readiness pozostają `not_ready`. Frozen source 2.7 zachowuje swoje
pierwotne false flags; późniejszy odbiór jest osobnym receipt, nie zmianą źródła.

## Odtwarzalny odbiór

```sh
services/api/.venv/bin/python -m scripts.data.verify_ai06_snapshot \
  --ai-repo /absolute/path/to/retailops-ai-intelligence \
  --ai-python /absolute/path/to/retailops-ai-intelligence/.venv/bin/python \
  --output ci-cd/reports/data/ai06/new-run/acceptance.json
```

Wybierz nowy katalog przebiegu. Odbiór wymaga clean runtime, obu standardowych
profili dwukrotnie i identycznych IDs. Budżet 300 s / 1024 MiB obejmuje source,
qualification, eksport, import, curated oraz niezależne as-of. Instalacja jest
poza pomiarem. Reimport/rebuild i private isolation mają osobne testy regresji.
[Końcowy audyt](../evidence/ai/06/final/README.md) zamyka zakres AI 06 i DATA-06.
Ocena 04/05 na nowych IDs jest wymagana przed 07/08, a model 08 ma własne gates.
