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

W ocenie RF origin jest o `23:59:59 UTC` dnia poprzedzającego pierwszy target.
Rekord dostępny później, nawet przed północą, nie wchodzi do tej prognozy.
Wszystkie dni horyzontu używają tej
samej historii. Kalendarz targetu, identyfikatory serii oraz kategoria i marka
produktu ze statycznego katalogu generatora są znane w origin. Lagi i okna RF
odnoszą się do dat kalendarzowych względem origin; brak dnia ma osobny wskaźnik.
Historia obejmuje tylko obserwacje dostępne najpóźniej w origin. Dla pojedynczego
wiersza kontraktu reguła `previous_day_end_utc` oznacza najwcześniejszy możliwy
origin jednodniowy; dłuższy horyzont może mieć wcześniejszy origin.
`observation_available_at` to maksimum czasu
ingestii sprzedaży i utworzenia zamówienia składających się na dany agregat;
gdy rekord sprzedaży nie ma czasu ingestii, używany jest `sold_at`. Taką samą
granicę stosuje baseline w ocenie RF. `units_sold` oraz
wyprowadzony z niego `observation_status` są etykietami. `generated_at` jest
metadanym wykonania, nie dowodem dostępności źródła w historycznym origin.
`observation_available_at` jest metadanym dostępności etykiety, nie cechą RF.
Manifest wymienia pola wejściowe, etykiety i metadane dostępności osobno.

Agregat zachowuje tylko najnowszą sumę i jej dostępność, bez wcześniejszych
wersji. Spóźniona sprzedaż historycznego dnia może przez to usunąć wcześniej
znaną obserwację z cech starego origin. Obecna ocena syntetyczna ma ingestie
w tym samym dniu; nie potwierdza odtwarzania historii z późniejszymi korektami.
To otwarte ograniczenie [ML-07](../audits/open-findings.md), do usunięcia
przed odbiorem takiej historii w AI 02–04.

Wiersz powstaje wyłącznie z jawnego rekordu sprzedaży połączonego z zamówieniem.
Suma `quantity=0` daje `observation_status=observed_zero`; dodatnia suma daje
`observed_positive`. Brak rekordu nie tworzy wiersza o zerowym targetcie, a brak
wartości `quantity` jest błędem. Obecny generator nie dostarcza wersjonowanego
asortymentu, kalendarza otwarcia sklepów ani watermarku kompletności. Dlatego
nie da się wiarygodnie zaklasyfikować nieobecnego wiersza jako zera, zamknięcia,
nieaktywności lub brakujących zdarzeń. Manifest deklaruje
`complete_daily_panel=false`: sam zbiór cech nie jest panelem. Osobny
[protokół oceny RF](../guides/ml.md) buduje pełny panel tylko dla profili
syntetycznych, przy jawnej deklaracji ich kompletności i statycznego asortymentu.
Nie wolno przenosić tego założenia na fixture `demo` ani zewnętrzne dane bez
wersjonowanego potwierdzenia kompletności, otwarcia i asortymentu.

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

Zmiana schematu `1.0` → `2.0`, RF `random-forest-v1` → `random-forest-v3`
oraz baseline `baseline-moving-average-v1` → `baseline-moving-average-v2`
oddziela nowe przebiegi od [historycznego snapshotu](../evidence/ml/random-forest-v1/README.md).
RF ocenia trzy chronologiczne okna walidacyjne oraz odłożony końcowy test, każdy
z jednym origin na cały horyzont. Wynik ma osobne pokrycie i pominięcia. Osobny
`make ml-evaluate` pozostaje kroczącym backtestem samego baseline i nie służy
do porównania z RF.

`dataset_id` zawiera profil, zakres dat i seed. Pełną konfigurację, logiczne
sumy danych i kod wiąże [tożsamość eksperymentu](../guides/ml.md), a nie sam
identyfikator datasetu. Manifest może wskazywać `quality_report.json` bez
kopiowania tego pliku do katalogu cech.
