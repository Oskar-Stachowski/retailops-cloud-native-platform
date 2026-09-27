# Kontrakt cech prognozy sprzedaży

Aktualny format tworzy [generator cech](../../ml/features/demand_forecast.py).
Polecenia uruchomienia opisuje [instrukcja ML](../guides/ml.md).

| Właściwość | Wartość |
|---|---|
| Nazwa datasetu | `retailops-demand-forecast-features` |
| Wersja schematu | `2.0` |
| Ziarno | `date`, `product_id`, `store_id`, `channel` |
| Target | `units_sold` — zaobserwowana liczba sprzedanych sztuk |
| Pliki | `features.csv`, `feature_manifest.json` |
| Domyślny katalog | `data/synthetic/<profile>/features/demand_forecast/` |

[Schemat wiersza](../../ml/contracts/demand_forecast_features.schema.json),
[schemat manifestu](../../ml/contracts/demand_forecast_feature_manifest.schema.json),
[przykład wiersza](../../ml/contracts/demand_forecast_features.example.jsonl)
i [przykład manifestu](../../ml/contracts/demand_forecast_feature_manifest.example.json)
są wersjonowane razem z kodem.

## Granica czasu i pochodzenie

W aktualnej ocenie kroczącej origin dla targetu dnia `D` to koniec dnia `D-1`
w UTC. Kalendarz dnia `D`, identyfikatory serii oraz kategoria i marka produktu
ze statycznego katalogu generatora są wejściami znanymi w tym origin. Lagi i
okna RF korzystają tylko z obserwacji wcześniejszych niż `D`, dla których
`observation_available_at` nie jest późniejsze niż origin. To maksimum czasu
ingestii sprzedaży i utworzenia zamówienia składających się na dany agregat;
gdy rekord sprzedaży nie ma czasu ingestii, używany jest `sold_at`. Taką samą
granicę stosuje baseline w ocenie RF. `units_sold` oraz
wyprowadzony z niego `observation_status` są etykietami. `generated_at` jest
metadanym wykonania, nie dowodem dostępności źródła w historycznym origin.
`observation_available_at` jest metadanym dostępności etykiety, nie cechą RF.
Manifest wymienia pola wejściowe, etykiety i metadane dostępności osobno oraz podaje
`forecast_origin_rule=previous_day_end_utc`.

Wiersz powstaje wyłącznie z jawnego rekordu sprzedaży połączonego z zamówieniem.
Suma `quantity=0` daje `observation_status=observed_zero`; dodatnia suma daje
`observed_positive`. Brak rekordu nie tworzy wiersza o zerowym targetcie, a brak
wartości `quantity` jest błędem. Obecny generator nie dostarcza wersjonowanego
asortymentu, kalendarza otwarcia sklepów ani watermarku kompletności. Dlatego
nie da się wiarygodnie zaklasyfikować nieobecnego wiersza jako zera, zamknięcia,
nieaktywności lub brakujących zdarzeń. Manifest deklaruje
`complete_daily_panel=false`; zbudowanie pełnego panelu i pokrycia jest częścią
[protokołu oceny](../plans/ml-evaluation.md).

Historia cen i promocje generatora nie dokumentują jednoznacznie wersji znanej
w każdym origin. Zrealizowana cena, przychód, rabat, stockout i prawda symulatora
z dnia targetu są wynikami dnia. Żadne z tych pól nie trafia do zbioru cech ani
do wejścia RF. Bieżący `product_status` także nie jest historycznie wersjonowany
i pozostaje wyłączony. Kategoria i marka są w obecnym generatorze stałe przez
cały okres; po dopuszczeniu ich zmian źródło będzie wymagać wersji z czasem
dostępności.

Snapshoty zapasu dotyczą magazynów (`warehouse_code`), podczas gdy grain
prognozy używa `store_id`. Brakuje mapowania sklepu i kanału do miejsca zapasu
obowiązującego w danym czasie. Zapas nie jest dopasowywany po samym produkcie,
nie ma fallbacku do późniejszego snapshotu i nie jest zamieniany na pozorne zero.
Nie ma żadnej cechy zależnej od zapasu; manifest deklaruje `inventory_ready=false`.
Przywrócenie takich cech wymaga mapowania fulfillment i wiarygodnego ledgeru.

## Zakres obecnej oceny

Zmiana schematu `1.0` → `2.0`, RF `random-forest-v1` → `random-forest-v2`
oraz baseline `baseline-moving-average-v1` → `baseline-moving-average-v2`
oddziela nowe przebiegi od [historycznego snapshotu](../evidence/ml/random-forest-v1/README.md).
Obecny backtest RF nadal czyta fakty z wcześniejszych dni holdoutu przy kolejnych
origin. Nie jest sprawdzeniem zamrożonej prognozy całego siedmiodniowego
horyzontu; tę zmianę obejmuje [kolejny krok planu](../plans/before-ai-00.md).

`dataset_id` zawiera profil, zakres dat i seed. Pełną konfigurację, logiczne
sumy danych i kod wiąże [tożsamość eksperymentu](../guides/ml.md), a nie sam
identyfikator datasetu. Manifest może wskazywać `quality_report.json` bez
kopiowania tego pliku do katalogu cech.
