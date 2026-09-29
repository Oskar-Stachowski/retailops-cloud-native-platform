# Karta source/snapshot/curated AI 03

**Wersja odbioru: 29.09.2026.** Dane syntetyczne, seed 42, source 2.6.0,
snapshot/handoff/curated 1.0.0. Przypięty kod i locki, config, watermarks,
counts/grain/ranges/checksums i SHA schematów: [verification.json](verification.json).
Pełne manifesty są wskazane w [odbiorze](README.md).

| Przypadek | Historia / produkty | Tabele / wiersze | Dopuszczony cel |
|---|---|---|---|
| `ai-smoke` | 30 dni / 20 | 25 / 31 171 | Development kontraktów i przygotowanie źródła do forecastingu |
| `ai-temporal-smoke` | 102 dni / 8; 28 warmup, 60 originów, 14 label tail | 25 / 52 973 | Odtworzenie ścieżki czasowej; nie ocena przewagi modelu |
| `controlled-late-fact` | 8 dni / 2 | 25 / 609 | Wyłącznie kontrolowany odbiór późnej korekty i as-of |

Koniec historii: 2026-07-31; 3 selling locations i 2 stock locations.
Kalendarze/business dates pochodzą ze źródła; instants mają UTC i mikrosekundy.
Jawne przyszłe plany i ogon zwrotów pozostają w swoich zakresach/watermarkach,
nie są obcinane do końca historii. Origin dopuszcza tylko właściwe znane wersje.

## Identity i lineage

Każdy parent source → snapshot → curated ma oddzielny niezmienny ID.
Pełne ID są poniżej; oba powtórzenia i oba systemy operacyjne dały ten sam wynik.

| Przypadek | Source / snapshot / curated |
|---|---|
| `ai-smoke` | `source-sha256-a12866e1099c3ae2ae7c73cac5c533a35733618d85a3728cd5f0e1c7b527fc00`<br>`snapshot-sha256-4d856185ebbe3a8f07dc468468c54eacf69aa40b7d49bfff7e39af8ddde815a4`<br>`curated-sha256-a5f0613c535ad004481ae104840537687da61551a3aceaa61d78af5eeb4cc10c` |
| `ai-temporal-smoke` | `source-sha256-94829460645140b79a6f68e87194f74d2c8e55392e2702a9fecbe6b771116d22`<br>`snapshot-sha256-d84c7b9630c6a34f7807abc7560253bf8e7ba3d7d962abee8aca580cf909b767`<br>`curated-sha256-aeedd1a49f75eb27b687b328b92e23fee5b8cfa7c2520b2ff5219a8a74bd748a` |
| `controlled-late-fact` | `source-sha256-e4e2c1e8a468355b497c7737768600882c8812e954707a5c71a91decbbdadeb7`<br>`snapshot-sha256-9525f559b344211843308e9435b5d3a3732e983f3ef6ba3ffb831644b257f2ba`<br>`curated-sha256-72ccf70807181dc9e2c1c356975788674637d98dd7b4281781083aedd9834d05` |

Canonical source 1.6 zachowuje NFC, UTC i normatywną precyzję Decimal 28;
typed parity odrzuca wartości, których nie można zachować w tej precyzji.
Curated canonical 1.0 zachowuje dokładne typed wartości, config, parents,
availability i fingerprints całego wykonywanego bundle oraz locka.
Aktualizacja importera zmienia fingerprint/curated ID przy niezmiennym source
i snapshot. Timestamp wykonania i lokalny katalog nie są logiczną identity.

## Znaczenie danych i readiness

Curated zachowuje 25 źródłowych facts/plans, wszystkie quantity versions,
row/grain/hash lineage i jawne product/selling/channel/stock mappings.
Jednostki ilości i waluty są sprawdzane przez wersjonowaną politykę;
nie powstają zastępcze SKU, magazyny, lokalizacje ani przypadkowe zera.
Gap/missing, zero i closed/inactive pozostają rozróżnione. Nieznana dostępność
statycznych/legacy atrybutów pozostaje `not_recorded`, bez wymyślonej historii.
Historia demand ma grain business_date/product/selling_location/channel/version;
as-of wybiera najwyższą wersję znaną w origin. Późna korekta nie nadpisuje starej.

Wszystkie 46 source hard gates przechodzą; quarantine = 0. Simulation truth
pozostaje poza curated, w osobnej przestrzeni opt-in parent importu, bez
automatycznego joinu lub dostępu aplikacji. Źródłowe AI outputs nie są facts.

| Zastosowanie | Obecny status |
|---|---|
| `forecast_source` | passed; wejście do AI 04 dla obserwowanej sprzedaży |
| `forecast_model` | not_ready; features/splits/trening/ocena należą do AI 04–05 |
| inventory | false; ledger i poprawne fulfillment mapping należą do AI 06 |
| anomaly / stockout / replay | not_ready; własne dane, labels i późniejsze bramki |
| RAG tych danych | not_applicable; odbiór RAG 11 jest odrębny |

Source readiness `forecasting=not_ready` nie jest zmieniana na gotowość modelu
przez importer. AI 04 pomija inventory features; target opisuje obserwowaną
sprzedaż, bez twierdzenia o niezaspokojonym popycie. Źródło syntetyczne i rozmiary
smoke nie dowodzą realizmu rynku ani zasobów pełnych ai-dev/ai-training.

Wygenerowane dane przechowuj pod ignored generated; manifesty i raporty mają
oddzielną retencję. Gotowych artefaktów nie nadpisuj. Po AI 06/07 utwórz nowe
source/curated IDs i ponów zależne oceny, zachowując poprzednie snapshoty.
