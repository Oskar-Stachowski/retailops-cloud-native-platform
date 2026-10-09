# Wersjonowany source inventory — AI 06.6b.2a

[Source 2.7](../../data/contracts/inventory_source_dataset.v2_7.schema.json)
łączy rzeczywistą sprzedaż z ledgerem, dostawami, zwrotami i projekcjami zapasu.
Tworzy własny niezmienny `source-sha256-*`. Domyślna ścieżka generatora/API
oraz exporter/importer 03 nadal korzystają z 2.6; przełączenie wymaga dalszego odbioru.
[Odbiór lokalny](../evidence/ai/06/06.6b.2a/README.md) opisuje zakres weryfikacji.

## Zawartość i znaczenie

Source zawiera **58 tabel CSV: 46 facts/plans oraz 12 simulation truth**.
[27 tabel inventory](inventory-source-tables.md) ma dotychczasowy ścisły kontrakt.
Pozostałe tabele zachowują kolumny handlu, wymiarów, planów, panelu i historii 2.6.
`return_events` jest jedną wspólną tabelą finansową z typowaną ilością całkowitą;
nie powstaje druga kopia refundów.

| Katalog | Zakres |
|---|---|
| `facts/` | Fakty handlowe, wymiary i plany oraz operational inventory/supply/disposition/snapshots. |
| `simulation_truth/` | Osiem private inventory tables, dotychczasowe product/store parameters, daily demand i promotion truth oraz prywatna konfiguracja symulacji. |
| Root | `dataset_manifest.v2.json`, raport source i diagnostyczny realism, każdy w JSON/MD. |

Losowe legacy inventory, prognozy, anomalie, alerty i workflow nie są częścią
tego source. Sprzedaż jest faktycznie wykonaną ilością; cena uwzględnia tę
ilość, a refund dotyczy faktycznego zakupu. Brak popytu, brak stock i brak
dostępnego faktu pozostają odrębnymi sytuacjami.

Panel, append-only history, cohorts i dzienne ceny używają causal availability.
Surowe sale ingestion pozostaje w transakcji; adapter nie przepisuje faktów.
Finansowy ogon zwrotów nie rozszerza fizycznego okna inventory.
Stockout episodes i diagnostyczne okna pozostają prywatnym truth;
Frozen `label_qualification=not_evaluated` dotyczy tych raw diagnostyk.
Aktualna [kwalifikacja lifecycle/coverage](inventory-label-qualification.md)
ma osobny immutable artefakt z parent source ID; nie przepisuje tego raportu.

## Identity, konfiguracja i odczyt

Eksport dla świeżej prognozy może jawnie dodać `--forecast-plan-days 14` do
`python -m data.export.ai_snapshot --profile ai-smoke --seed SEED --end-date DATE`.
Ten wariant source 2.7 używa generatora `0.9.1` i polityki
`known-forecast-plans-1.0.0`, przypiętych w requested/resolved parameters.
Kalendarze, końcowe okresy channel/route/assortment i znane ceny obejmują
zadeklarowane przyszłe dni. `end_date`, okno inventory oraz obserwacje pozostają
na rzeczywistym końcu historii. Ceny na przyszłe dni muszą być znane przed
origin zamykającym historię. Nie powstają przyszłe obserwacje ani watermarky.
Domyślne `forecast_plan_days=0` zachowuje poprzedni kształt parametrów i reguły.
CLI dopuszcza 7 lub 14 dni; odrzuca tę opcję dla źródła 2.6 i istniejącego source.
Oddzielny przegląd adaptera AI 05 przypina nowe source/snapshot IDs bez treningu.

Generator tej ścieżki ma wersję `0.9.0`, source `2.7.0`, canonicalization
`inventory-source-typed-csv-1.0.0`, policy `inventory-source-acceptance-1.0.0`.
Native ilości/sequence są integer, flagi boolean, nulle są jawne, pieniądze
mają dokładne dwie pozycje dziesiętne, a instants UTC i mikrosekundy.
Pozostałe CSV zachowują typowaną canonicalization kontraktów 2.6.
Każda tabela ma ścisły grain i stałe columns/classification.

Descriptor wiąże resolved generation, hash pełnej inventory configuration,
operational context i evaluation cutoff, schema hash, logical hashes wszystkich
tabel oraz fingerprints kodu i zależności. Timestamp uruchomienia i lokalna
ścieżka nie są logiczną identity. Prywatne supplier reliability/lead parameters
pozostają w `simulation_truth/inventory_configuration.json`, poza worker facts.
Domyślna konfiguracja jest zdefiniowana w runtime; seed pochodzi z generation.
`--inventory-config` pozwala podać jawny wersjonowany wariant.

[Writer/reader](../../data/inventory/source_dataset_io.py) weryfikuje cały staging
przed publikacją. Reuse odczytuje istniejący source i nie naprawia ani nie
nadpisuje jego plików. Kontroluje ID/provenance, table/file/column allowlist,
placement facts/truth, checksums, typy, nulle, grain i wszystkie zapisane rekordy.
CSV ma limit 128 MiB na plik, metadata 2 MiB; to ograniczony lokalny odbiór smoke.

[Quality](../../data/inventory/source_dataset_quality.py) ponownie wylicza
**36 bramek** z zapisanych tabel. Zachowuje gates wymiarów, cen i finansów,
a uncapped demand equality zastępuje uzgodnieniem `latent = observed + lost`.
Sprawdza native graph/projection, commerce/issue parity, wszystkie historyczne
route versions, config binding, private supplier realization oraz każde zamówienie
i initial plan względem znanych faktów w jego review origin. Przyszłe ruchy
i późniejsze zamówienia nie trafiają do odtwarzanego reorder review.
Causal history/cohorts są sprawdzane w swoim kanonicznym grainie;
legacy PAIR numbering nie zależy od kolejności CSV.

Czytnik nie generuje ponownie koszyków. Nie ufa zapisanym `passed`:
odtwarza raporty quality/realism i porównuje ich pełną treść.
Realism opisuje rzeczywisty udział zerowych fizycznych sald, epizody i utracone
sztuki, z jawnym denominator. Nie kwalifikuje modelu ani rozkładu produkcyjnego.

`facts_ready=true` oznacza przejście lokalnych gates tego source.
`source_ready=false`, `inventory_ready=false`, `model_ready=false` i
`publication_status=awaiting_ai03_handoff` pozostają obowiązkowe.
`not_ready` zachowuje poprawny source z brakującą availability;
naruszenie procesu/integralności daje `failed` bez publikacji katalogu.

## Uruchomienie

Opcjonalny [postęp operacji i rzeczywiste liczniki](../evidence/ml/ai09-source-live-progress.md)
można włączyć kontekstem `data.generator.progress.reporting` wokół natywnego
wywołania. Nie zmienia on semantyki danych ani kontroli walidacji.

Z katalogu głównego RetailOps:

```bash
services/api/.venv/bin/python -m data.inventory.run_source_dataset \
  --profile ai-smoke \
  --output-root ci-cd/reports/data/inventory-source-27 \
  --output ci-cd/reports/data/inventory-source-27-receipt.json
```

Receipt podaje gotowy katalog pod `source-sha256-*`. Można go ponownie
zweryfikować dotychczasowym entry pointem, którego dispatcher zachowuje
czytniki 2.0–2.6 i wybiera nowy kontrakt dla 2.7:

```bash
services/api/.venv/bin/python -m data.generator.manifest_v2 \
  --data-dir ci-cd/reports/data/inventory-source-27/source-sha256-<ID>
```

Powtarzalny odbiór wymaga czystego kodu na HEAD:

```bash
services/api/.venv/bin/python -m scripts.data.verify_ai06_source \
  --output ci-cd/reports/data/ai06-06b2a/acceptance.json
```

Przebiega od świeżego generatora przez nowy source, gates i ponowny odczyt;
oba standardowe profile wykonuje dwukrotnie. Obejmuje supply-poor,
zero opening, late availability i źródło bez popytu. Budżet 300 s / 1024 MiB
dotyczy tego lokalnego etapu, bez eksportu/importu/curated 03.

## Pełny odbiór AI 06

[Snapshot/curated 1.1](inventory-snapshots.md) publikuje tę warstwę przez
domyślną ścieżkę AI. [Końcowy audyt i odbiór](../evidence/ai/06/final/README.md)
obejmuje source/qualification/export/import/curated i historyczny as-of.
Frozen artefakty oraz manifest źródła zachowują dawne IDs i flagi; aktualne
readiness zapisują curated i końcowy receipt. Modele 04/05/08 mają własne gates.

Zwykły eksport producenta 0.9.0 zachowuje dokładne bajty schematów przypięte
przez dotychczasowych niezależnych importerów. Rozszerzona para schematów
trafia do snapshotu wyłącznie przy jawnym `forecast_plan_days` producenta
0.9.1. Weryfikacja wymaga całej zatwierdzonej pary; mieszanie lub dowolna
podmiana schematów jest odrzucana.
