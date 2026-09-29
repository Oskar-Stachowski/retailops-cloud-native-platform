# Snapshot inventory 1.1 — AI 06.6b.2c.1

[Lokalny odbiór](../evidence/ai/06/06.6b.2c.1/README.md) obejmuje exporter
w RetailOps i niezależny importer w repo AI. Wejściem są
[source 2.7](inventory-source-dataset.md) oraz
[qualification 1.0](inventory-label-qualification.md). Snapshot1.0/source 2.6
zachowuje osobne schemas i ścieżkę03; domyślny generator/API nadal korzysta z2.6.

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

## Odbiór i pozostały zakres

```sh
services/api/.venv/bin/python -m scripts.data.verify_ai06_snapshot \
  --ai-repo /path/to/isolated/retailops-ai-intelligence \
  --ai-python /path/to/isolated/retailops-ai-intelligence/.venv/bin/python \
  --output ci-cd/reports/data/ai06/new-run/acceptance.json
```

Wybierz nowy katalog przebiegu, aby worker sprawdził fresh import, następnie
reimport/verify. Odbiór wymaga clean runtime, obu standardowych profili dwukrotnie,
identycznych IDs i budget 300s/1024MiB dla source/qualification/export/import.
Nie obejmuje pending curated i nie jest pełnym odbiorem DATA-06.

**Następny zakres 06.6b.2c.2** to curated 1.1 z native grain, causal availability,
historycznym as-of i truth isolation, pełny pipeline/budget oraz przełączenie
domyślnego source AI. Curated1.0 odrzuca snapshot 1.1 jawnym kodem błędu.
Frozen source 2.7 zachowuje source/inventory/model readiness=false.
Nowe IDs wymagają ponownej oceny04/05; model 08 ma własne gates.
