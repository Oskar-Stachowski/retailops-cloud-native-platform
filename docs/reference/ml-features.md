# Kontrakt cech prognozy sprzedaży

Ten dokument opisuje aktualny format i implementację
[ml/features/demand_forecast.py](../../ml/features/demand_forecast.py).
Generowanie cech, baseline, trening RF i raportowanie są zaimplementowane;
instrukcja uruchomienia jest w [ML](../guides/ml.md).

| Właściwość | Wartość |
|---|---|
| Nazwa datasetu | `retailops-demand-forecast-features` |
| Wersja schematu | `1.0` |
| Ziarno | `date`, `product_id`, `store_id`, `channel` |
| Target | `units_sold` — obserwowana sprzedaż |
| Pliki | `features.csv`, `feature_manifest.json` |
| Domyślny katalog | `data/synthetic/<profile>/features/demand_forecast/` |

Schematy i przykłady pozostają przy kodzie:
[row schema](../../ml/contracts/demand_forecast_features.schema.json),
[manifest schema](../../ml/contracts/demand_forecast_feature_manifest.schema.json),
[przykład wierszy](../../ml/contracts/demand_forecast_features.example.jsonl)
i [przykład manifestu](../../ml/contracts/demand_forecast_feature_manifest.example.json).
Kanały to `store`, `online`, `marketplace` i `wholesale`.

## Pola i rzeczywiste pochodzenie

| Grupa | Pola | Budowanie w obecnej implementacji |
|---|---|---|
| Identyfikacja | `schema_version`, `dataset_id`, `feature_row_id`, `generated_at` | Nazwa/profil/zakres dat/seed, klucz wiersza i czasy źródeł |
| Ziarno | `date`, `product_id`, `store_id`, `channel` | Sprzedaż połączona z zamówieniem przez `order_reference` |
| Sprzedaż | `units_sold`, `sales_revenue`, `unit_price` | Suma ilości i przychodu; cena to przychód podzielony przez ilość |
| Cena i promocja | `discount_percent`, `promotion_active`, `promotion_type` | Porównanie z historią cen i dopasowanie aktywnej promocji |
| Zapas | `stockout_flag`, `inventory_on_hand`, `inventory_reserved` | Flagi sprzedaży i dopasowany snapshot zapasu |
| Produkt | `category`, `brand`, `product_status` | Rekord produktu |
| Kalendarz | `day_of_week`, `is_weekend`, `week_of_year`, `month` | Data biznesowa wiersza |
| Diagnostyka | `latent_units_demand`, `data_quality_status` | Prawda symulatora i statusy źródłowej sprzedaży |

Generator emituje również pola, które są opcjonalne w JSON Schema: m.in.
`latent_units_demand`, `promotion_type`, `inventory_reserved`, `product_status`,
`week_of_year`, `month` i `data_quality_status`. Nie są to zapowiedzi kolejnego
commitu. Jawny builder wejścia RF wybiera podzbiór cech; obecność pola w CSV
nie oznacza, że wolno użyć go do prognozy.

## Ograniczenia kontraktu v1

Wiersze powstają z istniejących rekordów sprzedaży. Builder nie uzupełnia pełnej
siatki dni, produktów, sklepów i kanałów. Brak wiersza nie jest jawnym zerem
sprzedaży. Zrealizowana cena i stockout tego samego dnia opisują wynik dnia,
więc nie są automatycznie cechami dostępnymi przed jego rozpoczęciem.

Dopasowanie zapasu odbywa się po produkcie; przy braku wcześniejszego snapshotu
kod dopuszcza późniejszy. `latent_units_demand` jest informacją symulatora,
a nie obserwowanym targetem do dowolnego zastosowania. Granice dostępności danych
i lokalizacji wymagają poprawek opisanych w [audycie](../audits/open-findings.md).

`dataset_id` zawiera profil, zakres dat i seed. Nie jest skrótem całej treści
ani pełnej konfiguracji; zmiana liczby produktów może pozostawić ten sam ID.
Manifest podaje liczebność, źródła, wersję generatora i datę wykonania, lecz samo
jego istnienie nie zapewnia niezmiennego, jednoznacznego pochodzenia eksperymentu.
Referencja `quality_report.json` nie oznacza, że job cech kopiuje ten raport do
katalogu cech — zapisuje dwa pliki wymienione powyżej.

## Zmiany i zgodność

Zmiana ziarna, targetu, typu wymaganego pola lub usunięcie pola wymaga jawnej
wersji kontraktu i aktualizacji konsumentów. Schemat ma `additionalProperties=false`,
więc także nowe pola wymagają aktualizacji schematu. Nowe eksperymenty powinny
wiązać wynik z kodem, pełną konfiguracją i treścią danych, zgodnie z
[planem oceny ML](../plans/ml-evaluation.md). Docelowy kontrakt osobnego serwisu
AI znajduje się w [planie AI](../plans/ai/kontrakty/dane-i-czas.md).
