# Niezmienny eksport do AI — 03.2

Eksporter `data.export.ai_snapshot` publikuje kwalifikowane źródło **2.6.0**
pod `data/generated/snapshots/<source_dataset_id>/`. Wersja snapshot manifestu
to **1.0.0**, polityka `retailops-ai-snapshot-1.0.0`, format
`retailops-parquet-1.0.0`. [Schemat JSON](../../data/contracts/ai_snapshot.v1.schema.json)
odpowiada wykonywalnemu modelowi. [Evidence](../evidence/ai/03/03.2/README.md)
opisuje lokalny odbiór. Kontrakt handoff, importer i curated są kolejnymi zakresami.

## Uruchomienie

Z katalogu głównego repo, po `make data-parquet-install`:

```bash
services/api/.venv/bin/python -m data.export.ai_snapshot \
  --profile ai-smoke --seed 42 --end-date 2026-07-31 \
  --output-root data/generated/snapshots
```

Można użyć `ai-temporal-smoke` i tych samych jawnych parametrów.
Generacja odbywa się w prywatnym katalogu tymczasowym. CLI zwraca JSON
z `publication=published|reused`, ścieżką oraz **pełnym manifestem**.
Domyślnym wymaganym zastosowaniem jest `forecast_source`.

Eksport już istniejących CSV wymaga podania ich dokładnego source ID:

```bash
services/api/.venv/bin/python -m data.export.ai_snapshot \
  --source-dir data/generated/ai03/example-csv \
  --dataset-id source-sha256-a12866e1099c3ae2ae7c73cac5c533a35733618d85a3728cd5f0e1c7b527fc00 \
  --output-root data/generated/snapshots
```

ID musi odpowiadać manifestowi tego katalogu. Ten tryb odrzuca parametry
generatora; tryb generacji wymaga profile, seed i end date oraz odrzuca dataset ID.
Nie korzysta z bieżącej daty, bazy RetailOps, brokera ani AWS.

`--require-use-case` można powtarzać. W źródle 2.6 gotowy jest wyłącznie
`forecast_source`; wymaganie forecasting, anomaly, stockout, replay lub rag
blokuje publikację. `inventory_ready=false` pozwala eksportować obserwowaną
sprzedaż i nie otwiera cech inventory ani oceny modeli.

## Zawartość i granica truth

```text
data/generated/snapshots/
  .staging/export-*/             # prywatny, niewidoczny jako gotowy dataset
  .locks/<source_dataset_id>.lock # koordynacja publikujących procesów
  <source_dataset_id>/
    snapshot_manifest.json
    manifest.sha256
    facts/<table>/[business_date=YYYY-MM-DD/]part-*.parquet
    evaluation_truth/<table>/... # wyłącznie po jawnej fladze
    schemas/                    # kontrakty i typy Arrow każdej tabeli
    reports/                    # 13 zweryfikowanych raportów źródła
    manifests/dataset_manifest.v2.json
```

Allowlista zawiera **25 tabel**: products, stores, warehouses, orders,
order_items, sales; dziewięć kanonicznych wymiarów; price_plans,
promotion_plans, sale_price_references, daily_price_observations;
daily_demand_observations, daily_demand_exclusions; return_policies,
return_events, daily_return_cohorts oraz **daily_demand_versions**.
Mapping store/warehouse pozostaje jawny; fizyczne stock locations nie oznaczają
kwalifikowanego stanu zapasu. Wszystkie wersje i `available_at` są zachowane.

Eksporter wyklucza users, legacy price_history/promotions/returns,
inventory_snapshots/stock_movements oraz wszystkie forecasts/anomalies/alerts/
recommendations/workflow_actions. Nie eksportuje danych osobowych użytkowników
ani źródłowych wyników AI. Źródło 2.6 nie dostarcza strumienia raw events.

Opcjonalna flaga `--include-evaluation-truth` dodaje cztery tabele do
**evaluation_truth**: promotion_effect_truth, daily_demand_truth,
product_simulation_parameters, store_simulation_parameters. Ten katalog ma
uprawnienia **0700**, cały bundle jest prywatny. Nie powstaje automatyczny join
ani mount w runtime/workerze. Procesy działające jako ten sam użytkownik systemu
nie mają tu odrębnej granicy uprawnień; consumer musi jawnie wybierać facts.
Wariant z truth należy publikować w osobnym `--output-root`.

## Walidacja, identity i publikacja

Eksporter najpierw kopiuje wszystkie źródłowe CSV i raporty do prywatnego stagingu,
kontroluje rozmiary/checksumy, a następnie na tej kopii **przelicza** kontrakty,
wymiary, ceny, popyt, zwroty, separację truth, historię, 46 hard gates i realism.
Późniejsza zmiana oryginalnego CSV nie zmienia danych, które czyta writer.
Allowlista dotyczy publikacji; pełne źródło jest potrzebne do kwalifikacji.

Przed publikacją ponowny odczyt sprawdza każdy byte SHA-256 i typed logical hash,
schema, counts, przypisanie tabel do namespace oraz zgodność dat partycji z wierszami,
także dat orders dla order_items. Brakujące/dodatkowe pliki i katalogi, symlinki,
path traversal, błędne ID, nieobsługiwana wersja i niespójna lineage są odrzucane.
`manifest.sha256` kontroluje manifest bez referencji do samego siebie.

**Source ID** zachowuje identity całego źródła, również tabel nieeksportowanych.
**Snapshot ID** identyfikuje jego wybraną projekcję: parent source, policy/format,
wykonywany kod eksportu i lock zależności, schemas, kwalifikację, wymagane use cases,
truth flag oraz logiczne artefakty. Descriptor nie zawiera własnego ID,
generated_at, lokalnych ścieżek, bieżącego Git SHA ani physical byte hashes.
Zmiana chunk/partycji lub metadanych wykonania nie zmienia snapshot ID.
Commit i dokładne physical references pozostają w pełnym manifeście.

Po weryfikacji i fsync kompletny katalog publikuje się jednym atomowym rename
z zakazem zastąpienia destination: Linux `renameat2(RENAME_NOREPLACE)` albo
macOS `renamex_np(RENAME_EXCL)`. Brak wsparcia kończy się błędem.
Blokada per source ID koordynuje równoległe eksporty; kernel chroni również
przed nadpisaniem pustego katalogu. Snapshot jest niezmienny w interfejsie eksportu.

Ponowny eksport kwalifikuje wejście i weryfikuje istniejący bundle. Zgodny
descriptor zwraca `reused` i zachowuje wszystkie wcześniejsze bajty.
Inna projekcja/transformacja pod tym source ID oznacza konflikt i wymaga osobnego
output root. Eksporter nie naprawia ani nie nadpisuje uszkodzonego snapshotu.
Przechowuj snapshoty na lokalnym filesystemie wspierającym te operacje.

Obsłużona awaria sprząta staging; twarde przerwanie procesu może go pozostawić.
Gotowe są wyłącznie katalogi source ID. Do pozostałego stagingu stosuj
[kontrolowany cleanup](parquet-artifacts.md#git-fixtures-i-cleanup), po zakończeniu
używających go procesów. Nie usuwaj aktywnych plików `.locks`.

## Bramki i ograniczenia

`make data-parquet-check` uruchamia Bandit high/high, regresje formatu/snapshotu
oraz dwa pełne przebiegi obu smoke w świeżych procesach. Każdy mierzy generację,
kwalifikację, eksport/odczyt i niezmienny re-export. Polityka
`ai03-snapshot-budget-1.0.0` ma limit **300 s / 1024 MiB peak RSS na profil**;
instalacja zależności jest poza pomiarem. Timeout joba Data CI to 30 minut.
Powtórzenia muszą zachować source ID, snapshot ID i wszystkie logiczne hashe.

Writer, sort hashy i indeks dat są porcjowane/dyskowe. Generator oraz pełna
walidacja źródła nadal materializują tabele w pamięci. Wyniki smoke nie kwalifikują
pełnego ai-dev/ai-training. Snapshot jest gotowym eksportem, nie gotowym curated
datasetem ani modelem. 03.3 przygotuje mały handoff bez generatora; 03.4/03.5
wykonają importer/curated, a 03.6 dopiero otworzy 04 i 06.
