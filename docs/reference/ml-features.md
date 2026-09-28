# Kontrakt cech prognozy sprzedaży

[Generator](../../ml/features/demand_forecast.py) rozdziela pełny panel AI
od legacy używanego przez demo i RF. Polecenia:
[instrukcja ML](../guides/ml.md), [generowanie źródła](../guides/data.md).

| Właściwość | AI | Legacy demo/small/medium/large |
|---|---|---|
| Schema | 3.1 | 2.1 |
| Grain | date/product_id/selling_location_id/channel | date/product_id/store_id/channel |
| Target | units_sold, target_type=observed_sales_units | units_sold |
| Coverage | Pełny aktywny panel źródłowy | Sparse agregaty sprzedaży |
| Statusy | observed_positive, observed_zero, closed, missing | observed_positive, observed_zero |
| Historia | observation_history: kanoniczny JSON wersji ilości/statusu/availability | Ten sam kontrakt wersji, bez domyślnego zera dla sparse dnia |
| Inventory | Bez kolumn zapasu; inventory_ready=false | Bez kolumn zapasu; inventory_ready=false |

Obie wersje zapisują features.csv, feature_manifest.json i feature_identity_manifest.json.
Domyślny katalog: data/synthetic/<profile>/features/demand_forecast/.
Historyczne cechy 2.0/3.0 i source 2.0–2.5 zachowują własne IDs i parent.

## Pełny panel AI 3.1

[Schema wiersza](../../ml/contracts/demand_forecast_features.v3_1.schema.json) i
[manifestu](../../ml/contracts/demand_forecast_feature_manifest.v3_1.schema.json)
wersjonują fizyczny grain. Wiersze pochodzą z
[daily_demand_observations i daily_demand_versions](daily-demand.md), katalogu i kategorii.
Nie są rekonstruowane ze sparse sales ani iloczynu dowolnych kanałów.
Inactive combinations mają osobny eksport wykluczeń, poza mianownikiem panelu.

Observed zero wymaga kompletnego otwartego dnia źródłowego, bez sztucznej
transakcji quantity=0. Closed ma zero i oddzielny status. Missing ma null label
i source_data_complete=false, nie jest zerem. Kompletny eksport blokuje missing
oraz luki w grain. complete_daily_panel=true nie oznacza gotowości modelu.

Bieżące observation_available_at to czas ostatniej wersji. Pierwszy stan
kompletnego dnia nie może poprzedzać zamknięcia źródła. Source watermark panelu
ma complete_through=end_date i cutoff następnej północy, bez gwarancji
kompletności legacy zwrotów ani ledgeru. Generated_at nie jest cechą ani
czasem dostępności wiedzy.

[Admission i izolowany worker](source-acceptance.md) wymagają source 2.6 i
`--source-dir`. Worker dostaje cztery projekcje faktów, bez generatora, katalogu
źródłowego, inventory, realized price/revenue, truth ani parametrów symulacji.
Transformacja `daily-demand-history-worker-1.0.0` i pełny fingerprint siedmiu
plików wykonywanego bundla wchodzą do logicznej identity.

## Odczyt historii dla origin

[Wspólny moduł](../../ml/features/observation_history.py) wymaga ciągłych wersji
od 1 i ściśle rosnącego UTC available_at. Korekta dopisuje stan, nie przepisuje
wcześniejszej wersji. Dla cutoff wybiera ostatni znany stan i ogranicza historię
do znanego prefiksu. Brak znanej wersji ma `missing_history`; missing zachowuje null.

Calendar lag wyznacza dokładną datę origin_day minus lag_days. Używa tylko
otwartych, kompletnych obserwacji znanych do origin. Luka, missing/closed lub
brak znanej wersji dają unknown. Nie przesuwa wcześniejszego sparse wiersza.
Dodanie późnej sprzedaży albo korekty nie zmienia wcześniejszego lagu.

Legacy agreguje wersje sprzedaży według availability: nowy sale ID dodaje ilość,
a późniejsza wersja tego samego ID zastępuje jego poprzednią ilość. RF i baseline
wybierają znane wersje wejść, a trening także labels dostępne w fold origin.
Późniejsza korekta może zmienić final actual, lecz wcześniejsze features,
training examples i predictions pozostają identyczne.

## Legacy 2.1 i RF

[Schema wiersza](../../ml/contracts/demand_forecast_features.schema.json),
[manifestu](../../ml/contracts/demand_forecast_feature_manifest.schema.json) i
[przykłady](../../ml/contracts/demand_forecast_features.example.jsonl) opisują 2.1.
Sparse eksport nie tworzy zer bez transakcji; complete_daily_panel=false.
Protokół RF uzupełnia panel tylko dla syntetycznych profili przy jawnych
założeniach z instrukcji ML. Wiersze kompletnego zera również zachowują historię.

Nowe przebiegi RF używają 2.1. Dawne snapshots 2.0/3.0 są czytelne i nie
otrzymują wymyślonych wcześniejszych wersji. Forecasting na pełnym panelu 3.1
wymaga implementacji i oceny AI 04 po snapshot/import/curated z AI 03.
Ostatnia [ocena RF](../evidence/ml/fixed-origin-rf-2026-09-27/README.md) pozostaje
rejected; zmiana kontraktu nie kwalifikuje modelu do serving.
