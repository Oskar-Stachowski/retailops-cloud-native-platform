# Przekazanie snapshotu RetailOps → AI — 03.3

Wspólny kontrakt **`retailops-source-snapshot-handoff` 1.0.0** przyjmuje snapshot
**1.0.0**, źródło **2.6.0**, format `retailops-parquet-1.0.0` i kanonizację
`typed-csv-nfc-utc-multiset-1.6.0`. Inne wersje wymagają jawnego odbioru;
nieobsługiwany major jest błędem. To kontrakt przekazania plików, bez generatora,
operacyjnej bazy, brokera ani AWS w repo AI.

## Pakiet dla nowej osoby w projekcie

Przekazujemy dokładnie [jeden fixture](../../data/fixtures/ai-smoke-v1):

```text
data/fixtures/ai-smoke-v1/
  contract.json                 # wersje, schematy tabel i zasady odczytu
  expected_manifest.json        # oczekiwane IDs, counts, dates i wszystkie byte SHA
  snapshot/
    snapshot_manifest.json      # pełny manifest i lineage
    manifest.sha256
    facts/<table>/part-000000.parquet
    schemas/                    # samowystarczalne JSON schemas i Arrow field schemas
    reports/                    # kwalifikacja całego source
    manifests/dataset_manifest.v2.json
```

[Kontrakt maszynowy](../../data/contracts/source_snapshot_handoff.v1.json)
jest identyczny z `contract.json` w obu repo. Fixture to pełny `ai-smoke`:
**25 tabel, 31171 wierszy, 74 pliki snapshotu**, seed 42, 20 produktów,
3 stores, 2 warehouses i 30 dni **2026-07-02–2026-07-31**.
Return tail i availability wychodzą poza ten okres; zakres każdego pola
podają expected manifest i source manifest. Nie obcinaj ich do end date.

Pakiet ma **2048665 B**. Razem z sześcioma archiwami regresji RetailOps:
**4484021 B / 5242880 B** po rozpakowaniu. Dane generated pozostają poza Git.
Fixture nie zawiera users, operational AI outputs, inventory ani truth.
Wykluczone tabele występują w pełnej metadata lineage źródła, ich CSV nie są
plikami snapshotu i konsument nie powinien ich szukać.

Source ID:
`source-sha256-a12866e1099c3ae2ae7c73cac5c533a35733618d85a3728cd5f0e1c7b527fc00`.
Snapshot ID:
`snapshot-sha256-4d856185ebbe3a8f07dc468468c54eacf69aa40b7d49bfff7e39af8ddde815a4`.
Snapshot pochodzi z eksportera na `6561481`; pakowanie nie przepisuje jego
provenance ani generated_at i nie zmienia source/snapshot ID.

## Grain, pola, jednostki i mapping

`contract.json` podaje dla każdej tabeli dokładne columns/types/nullability,
grain, data_class i temporal_role. To wykonywalna granica dla konsumenta;
schematy nie odwołują się do kodu generatora ani zewnętrznych `$ref`.

| Grupa | Grain / sposób odczytu |
|---|---|
| Products/catalog/categories | ID; `products.id = product_catalog.id`, SKU i jednostki z catalog |
| Stores/warehouses | Legacy compatibility ID; używać jawnych assignment/route mappings |
| Channel assignments/fulfillment/assortment | Stabilne ID rekordu; business key + version + validity + availability wybierają stan |
| Orders/items/sales/return events | ID transakcji/pozycji/zdarzenia; powiązania przez jawne source references |
| Business/category calendar | Date + selling location + channel; date + category |
| Plans | ID; wersje i scope produktu/kanału/lokalizacji, known/available time |
| Daily price/demand/exclusions | Date + product + selling location + channel |
| Daily demand versions | Ten sam daily grain **+ version**, nie collapse do latest |
| Return policies/cohorts | Category + channel; daily grain + as_of_time |

`selling_location_id` pochodzi z `selling_locations`. `channel_assignments`
wiąże legacy store i kanał z selling location; `fulfillment_routes` wskazuje
physical stock location. Wybieraj rekord o `effective_from <= business_date <
effective_to` oraz `available_at <= origin`, z właściwą wersją. Brak mappingu
wymaga błędu/kwarantanny z lineage; nie wybieraj losowego sklepu/magazynu.
Istniejący mapping stock location nie kwalifikuje inventory features.

Quantity oznacza liczbę saleable packs; `pack_quantity`/`pack_unit` opisują
zawartość fizyczną. Zachowuj source currency. Money to `decimal128(38,2)`,
pozostałe współczynniki `decimal256(76,40)`; canonical hash nie używa float.
Kanały: store, online, marketplace, wholesale. Null, zero i closed są różne.

## Czas, hash i gotowość

Timestampy mają UTC i dokładność mikrosekundy. `business_timezone=UTC`;
Europe/Warsaw/Berlin w lokalizacji są metadata kalendarza, nie zmianą granicy
business date. Origin jest dokładnym inclusive cutoff wiedzy.
Używaj wersji `available_at <= origin`; późna korekta nie zmienia starego origin.
Nie zastępuj historii najnowszym rekordem. Watermark oznacza zadeklarowaną
granicę/kompletność strumienia; nie maksimum dowolnej daty w Parquet.

Kanonizacja JSON: sorted keys, UTF-8/NFC, bez whitespace separatorów i NaN.
Decimals: finite, normalize przy precision 28, zapis fixed notation jako string,
zero jako `"0"`. Daty: ISO day; timestampy: UTC `datetime.isoformat()` z `+00:00`.
Hash tabeli to SHA256 headeru ordered columns + LF i canonical JSON wierszy
posortowanych według bajtów UTF-8, każdy z LF. **Duplikaty pozostają**.
Istniejący `logical_rows_sha256` w wire contracts AI stosuje inne zasady i
nie zastępuje tego algorytmu. IDs hashują descriptor, byte SHA transport osobno.

46 źródłowych hard gates jest passed. Gotowy jest **forecast_source**;
forecasting, anomaly, stockout i replay pozostają not_ready, rag not_applicable,
`inventory_ready=false`. Fixture nie kwalifikuje modelu ani stockout labels.
Opcjonalna evaluation truth ma osobny namespace w kontrakcie; ten fixture jej
nie zawiera. Przyszły importer nie może automatycznie udostępniać jej API/cechom.

## Polecenia i kolejność odbioru

RetailOps weryfikuje również typed content wszystkich tabel:

```bash
services/api/.venv/bin/python -m pytest -q data/tests/test_handoff.py
make data-parquet-check
```

Odtworzenie pakietu z tego samego zamrożonego snapshotu:

```bash
services/api/.venv/bin/python -m data.handoff.fixture \
  --snapshot-dir data/fixtures/ai-smoke-v1/snapshot \
  --output-dir data/generated/handoff/reproduced-ai-smoke-v1
```

Nowy output musi nie istnieć; pakowanie nie nadpisuje fixture ani snapshotu.
Świeża generacja/eksport może mieć nowe execution metadata i physical SHA;
po przeliczeniu gates trzeba jawnie zaktualizować expected manifest obu repo.

W repo AI: `make handoff-check` lub `uv run --locked python
scripts/check_snapshot_handoff.py`. Checker korzysta tylko z lokalnego kontraktu,
expected manifest i fixture; ma test odłączonego pakietu uruchomionego z `python -I`
dwukrotnie. Sprawdza schema, wersje, identity, allowlistę i wszystkie byte hashes.
[Typed importer 03.4](../evidence/ai/03/03.4/README.md) ma lokalny odbiór
Parquet/canonical hashes i atomowej publikacji do generated w repo AI.

Zmiany upstream i konsumenta mają osobne commity/branche ze wspólną wersją.
Najpierw dostarcz upstream fixture/contract, potem consumer registry/testy.
[Evidence 03.3](../evidence/ai/03/03.3/README.md) wskazuje rewizje i lokalne kontrole.
Curated to 03.5, pełna bramka obu repo to 03.6; dopiero ona otwiera 04 i 06.
