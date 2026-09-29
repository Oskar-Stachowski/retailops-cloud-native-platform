# Typowane tabele inventory — AI 06.6b.1

[Kontrakt](../../data/contracts/inventory_source_tables.v1.schema.json)
`inventory-source-tables-1.0.0` opisuje **27 tabel**. Powstają z wyniku
[integracji koszyków](source-inventory-commerce.md) i pełnych
[projekcji ledgeru](inventory-projections.md), z własnym fizycznym grainem.
[Odbiór lokalny](../evidence/ai/06/06.6b.1/README.md) dotyczy tego rozszerzenia.

To kandydat tabel przygotowany do włączenia w nową wersję source. Domyślny
source 2.6, exporter/importer 03 i curated 1.0 nadal używają dotychczasowych
kontraktów. Tego katalogu nie przekazuj loaderowi demo ani importerowi 03.
`source_ready`, `inventory_ready` i `model_ready` pozostają `false`.

## Tabele i rozdzielenie informacji

| Klasa | Tabele |
|---|---|
| Operational facts/plans — 19 | `inventory_products`, `inventory_stock_locations`, `inventory_scope`, `inventory_ledger`, `inventory_selling_locations`, `inventory_fulfillment_routes`, `inventory_route_versions`, `suppliers`, `product_suppliers`, `replenishment_orders`, `delivery_plan_versions`, `replenishment_receipts`, `inventory_sales`, `inventory_returns`, `return_events`, `return_inventory_decisions`, `inventory_history_coverage`, `inventory_reorder_rules`, `inventory_daily_snapshots` |
| Private simulation truth — 8 | `inventory_demand_arrivals`, `inventory_demand_outcomes`, `inventory_supplier_samples`, `inventory_scheduled_receipt_tail`, `inventory_physical_daily_balances`, `stockout_episodes`, `inventory_lost_sales_impacts`, `inventory_window_diagnostics` |

Facts/plans trafiają do `facts/`, a truth do `simulation_truth/`.
Operational tables nie zawierają latent/lost demand, przyszłych onsetów,
rzeczywistego opóźnienia dostawcy ani jego sampled disruption.
Financial return zachowuje odrębne availability od decyzji przyjęcia do stock.
Receipt w przyszłym tailu pozostaje truth i nie staje się ruchem ledgeru.

[Modele tabel](../../data/inventory/source_tables_contract.py) zabraniają
dodatkowych pól i wymagają jawnych nulli. Każda tabela ma ścisły grain
i deklarowaną klasę. Minimalne inventory masters zachowują identyfikatory
kanonicznego source; nie tworzą dodatkowego stock dla kanałów.
`inventory_route_versions` zachowuje oryginalną source version oraz lokalną
inventory revision. `TableContext` wiąże opening, znaną politykę reorder,
okno projekcji i cutoff oceny; nie zawiera supplier truth ani latent parameters.

## Typy, zapis i odczyt

[Writer/reader](../../data/inventory/source_tables_io.py) zapisuje każdą tabelę
jako CSV i Parquet. Ilości i sequence są `int64`, flagi `bool`, kwoty
`decimal128(38,2)`, daty `date32`, a timestamps `timestamp(us,UTC)`.
Brak wartości jest nullem, także w pustej tabeli. Pusta sprzedaż zachowuje
ten sam kompletny Parquet schema.

Manifest `tables.json` przypina kontrakt, context, parent execution ID,
grain/classification, liczbę wierszy, schema hash, logical hash oraz checksums
obu plików. ID `inventory-tables-candidate-sha256-*` wynika z kontraktu,
contextu, parent execution i kanonicznych tabel uporządkowanych według grainu.
Nie jest `source_dataset_id`, `snapshot_id` ani `curated_dataset_id`.

Zapis powstaje w staging i przenosi kompletny, zweryfikowany katalog.
Ponowne wykonanie odczytuje istniejący wynik i nie nadpisuje go.
Czytnik odrzuca obce pliki, symlinki, inne placement/grain, zmiany schema,
checksums, ID i próby deklaracji source/model readiness. Porównuje wszystkie
wiersze CSV/Parquet wraz z typami; Parquet czyta porcjami po 8192 wiersze.
Pojedynczy plik ma limit 128 MiB w tym lokalnym, ograniczonym odbiorze.

[Reconciler](../../data/inventory/source_tables.py) odtwarza ledger, supply
i commerce bez uruchamiania generatora. Ponownie sprawdza wydania, mapping,
refund/disposition/physical restock, popyt i jego kompletność względem arrivals,
wszystkie snapshoty, salda fizyczne, epizody, impacts oraz dojrzałość okien.
Weryfikuje scope policy/history, route lineage oraz ilości wszystkich
wykonanych i zaplanowanych receipts względem zamówień.
Cached timestamps i sumy prefiksowe przyspieszają odczyt; nie zmieniają
zapisanych ruchów, kolejności timestamp/sequence ani historycznej availability.

## Uruchomienie

Najpierw wygeneruj prywatny kandydat 06.6a:

```bash
services/api/.venv/bin/python -m data.inventory.run_source_commerce \
  --profile ai-smoke \
  --inventory-config data/tests/fixtures/source-inventory-config-v1.json \
  --output ci-cd/reports/data/inventory-source-parent.json
```

Następnie materializuj i odczytaj typowane tabele:

```bash
services/api/.venv/bin/python -m data.inventory.run_source_tables \
  --candidate ci-cd/reports/data/inventory-source-parent.json \
  --output-root ci-cd/reports/data/inventory-tables \
  --output ci-cd/reports/data/inventory-tables-receipt.json
```

`passed`/exit 0 oznacza spójny kandydat tabel. `not_ready`/exit 1 zachowuje
status niegotowego parent source, mimo poprawnego zapisu tabel.
`failed`/exit 1 oznacza naruszenie kontraktu, procesu lub integralności.
Domyślny cutoff diagnostyki to koniec okna; opcjonalny `--evaluated-at`
nie może poprzedzać obserwacji. Gotowy target/model 08 wymaga dodatkowej
kwalifikacji lifecycle/coverage — ten odbiór ma `not_evaluated`.

[Powtarzalny odbiór](../../scripts/data/verify_ai06_tables.py) wykonuje oba
standardowe profile dwukrotnie, supply-poor, zero opening, późną availability
i odrzucenie uszkodzonego parent. Wymaga czystego runtime na przypiętym HEAD:

```bash
services/api/.venv/bin/python -m scripts.data.verify_ai06_tables \
  --output ci-cd/reports/data/ai06-06b1/acceptance.json
```

## Następny zakres

[Source2.7 — 06.6b.2a](inventory-source-dataset.md) włącza te modele w osobny
wersjonowany source: identity, konfigurację, manifest oraz quality/realism.
Następne 06.6b.2b kwalifikuje lifecycle/coverage; potem trzeba przełączyć
domyślną ścieżkę AI, opublikować nowy immutable snapshot i rozszerzyć importer
na osobnym branchu repo AI i odebrać curated oraz pełny budżet cross-repo.
Reevaluation 04/05 i kwalifikacja modelu 08 pozostają odrębnymi bramkami.
DATA-06 jest nadal otwarte; pełny odbiór AI 06 nie został zadeklarowany.
