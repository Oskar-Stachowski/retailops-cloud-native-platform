# Kontrakt cech prognozy sprzedaży

[Generator](../../ml/features/demand_forecast.py) rozdziela pełny panel AI
od legacy używanego przez demo i obecną ocenę RF. Polecenia:
[instrukcja ML](../guides/ml.md), [generowanie źródła](../guides/data.md).

| Właściwość | AI | Legacy demo/small/medium/large |
|---|---|---|
| Schema | 3.0 | 2.0 |
| Grain | date/product_id/selling_location_id/channel | date/product_id/store_id/channel |
| Target | units_sold, target_type=observed_sales_units | units_sold |
| Coverage | Pełny aktywny panel źródłowy | Sparse agregaty sprzedaży |
| Statusy | observed_positive, observed_zero, closed, missing | observed_positive, observed_zero |
| Inventory | Bez kolumn zapasu; inventory_ready=false | Bez kolumn zapasu; inventory_ready=false |

Obie wersje zapisują features.csv, feature_manifest.json i feature_identity_manifest.json.
Domyślny katalog: data/synthetic/<profile>/features/demand_forecast/.

## Pełny panel AI 3.0

[Schema wiersza](../../ml/contracts/demand_forecast_features.v3.schema.json) i
[manifestu](../../ml/contracts/demand_forecast_feature_manifest.v3.schema.json)
wersjonują fizyczny grain. Wiersze pochodzą z
[daily_demand_observations](daily-demand.md), kanonicznego katalogu i kategorii.
Nie są rekonstruowane ze sparse sales ani iloczynu dowolnych kanałów.
Inactive combinations mają osobny eksport wykluczeń, poza mianownikiem panelu.

Observed zero wymaga kompletnego otwartego dnia źródłowego, bez sztucznej
transakcji quantity=0. Closed ma zero i oddzielny status. Missing ma null label
i source_data_complete=false, nie jest zerem. Kompletny eksport blokuje missing
oraz luki w grain. Manifest ma complete_daily_panel=true po bramce demand;
nie jest to ML readiness.

Observation_available_at to maksimum następnej północy UTC oraz ingestii i
cutoff wyceny faktów. Nie może poprzedzać zamknięcia źródła. Source watermark
panelu ma complete_through=end_date i cutoff następnej północy, bez gwarancji
kompletności legacy zwrotów ani ledgeru. Generated_at w wierszu jest
deterministycznym metadanym eksportu, nie cechą ani dowodem dostępności wiedzy.

[Moduł cech](../../ml/features/ai_demand.py) używa jawnych kolumn faktów i odrzuca
pola truth. Macierz nie zawiera inventory, realized price/revenue, multipliers
ani noise. Target i status są labelami, availability metadanym. Builder sprawdza
upstream gates; pełna izolacja procesu/runtime od truth jest dalszą pracą 02.

Calendar lag wyznacza datę origin_day minus lag_days, gdzie origin jest końcem
dnia przed pierwszym targetem. Używa tylko otwartych, kompletnych obserwacji
znanych do origin. Brak daty, missing/closed i późny rekord dają unknown, bez
podstawiania wcześniejszego sparse wiersza. Obsługuje także booleans z CSV.

Nowy zestaw ma logiczny features-sha256 ID, parent source 2.3 i transformację
daily-demand-panel-features-1.0.0. Source identity wiąże dane, kontrakty, kod i
zależności. Historyczne source 2.0/2.1/2.2 i feature 2.0 zachowują IDs i parent.

## Legacy 2.0 i istniejący RF

[Schema wiersza](../../ml/contracts/demand_forecast_features.schema.json),
[manifestu](../../ml/contracts/demand_forecast_feature_manifest.schema.json) oraz
[przykłady](../../ml/contracts/demand_forecast_features.example.jsonl) pozostają
formatem demo i obecnego RF. Wiersz pochodzi z jawnej sprzedaży i zamówienia.
Brak transakcji nie tworzy zera; complete_daily_panel=false. Osobny protokół RF
uzupełnia panel tylko dla syntetycznych profili przy założeniach z instrukcji ML.

RF i baseline używają dat kalendarzowych, wcześniejszych obserwacji znanych
w origin o 23:59:59 UTC i tego samego zamrożonego horyzontu. Nie korzystają
z przyszłych cen zrealizowanych ani zapasu. Obecny RF wymaga schema 2.0;
cechy 3.0 wymagają osobnej implementacji/oceny AI 04. Nie porównuj automatycznie
modeli na różnych snapshotach. Ostatnia [ocena RF](../evidence/ml/fixed-origin-rf-2026-09-27/README.md)
pozostaje rejected. Historia korekt i pełna lineage są częścią
[ML-07](../audits/open-findings.md), etapów AI 03–04.
