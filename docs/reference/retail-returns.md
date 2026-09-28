# Chronologia i zwroty profili AI

[Profile](data-profiles.md) · [Panel sprzedaży](daily-demand.md) · [Ceny](retail-pricing.md)

Source schema **2.4.0**, generator **0.6.0** i kanonizacja **1.4.0** dodają
`retail-returns-1.0.0`. AI eksportuje 37 CSV; legacy zachowuje 17 i wcześniejsze
bajty. [Schema](../../data/contracts/retail_returns.v1.schema.json) opisuje komórki
CSV, a [walidator](../../data/generator/return_quality.py) sprawdza semantykę.
To syntetyczna polityka generatora, bez deklaracji zasad prawnych lub kalibracji rynku.

| Tabela | Znaczenie |
|---|---|
| return_policies | Plan znany przed początkiem historii: kategoria/kanał, długość okna i maksymalne opóźnienie dostępności. |
| return_events | Zdarzenie konkretnej sale/order/item, fizyczna lokalizacja i kanał, ilość, refund, reason/status, returned/ingested/available time i policy ID. Zawiera także późniejszy ogon. |
| daily_return_cohorts | Rozliczenie kohorty dnia sprzedaży/product/location/channel w dwóch jawnych cutoffach: history i return_tail. Gross/refund/net revenue, observed/returned/net units i dojrzałość okna. |

## Okna i zdarzenia

Okno kategorii w dniach: Electronics 14, Home Improvement 21, Grocery 3,
Fashion 30, Beauty 7, Sports 21, Toys 14, Pet Care 7. Kanał dodaje:
store/wholesale 0, online 3, marketplace 7. Deadline to sold_at + okno;
granica jest włączona. Timestampy mają UTC; kalendarz lokalny nie zmienia
czasu trwania okna. Polityka musi być znana przed ordered_at.

Losowanie zwrotu używa oddzielnego RNG seed/sale/policy. Prawdopodobieństwo
wykorzystuje return_rate produktu i mnożnik kanału; parametry generatora
pozostają częścią otwartego zakresu izolacji truth DATA-05.
Zwrot następuje 1–window_days po sprzedaży. Ilość to 1–purchased quantity;
czasem dzieli się na dwa częściowe zgłoszenia. Suma wszystkich zgłoszonych
ilości, również odrzuconych, nie przekracza zakupu — to świadomie uproszczona
polityka bez ponownych zgłoszeń odrzuconych sztuk.

Status refunded zwraca quantity × rzeczywistą zapłaconą unit_price, także
po rabacie/bundle; rejected ma refund 0 i nie zmniejsza net units/revenue.
Powody: wrong_size, damaged, changed_mind, not_as_described, defective.
Nie ma niedomkniętych pending ani modelu przejść statusów. Availability następuje
po returned_at, maksymalnie po 2 dniach. Nie są modelowane korekty wersji zwrotu.

## Wiedza w cutoffie i ogon zwrotów

`ordered_at <= sold_at <= returned_at <= sold_at + window`; dodatkowo
returned_at ≤ ingested_at ≤ available_at. Zdarzenie trafia do rozliczenia
tylko gdy wszystkie trzy czasy są ≤ as_of_time. Sam czas zdarzenia nie
uprawnia do użycia zwrotu jeszcze niedostępnego w źródle.

`daily_demand_observations` zapisuje net revenue i return units **według wiedzy
przy zamknięciu własnego dnia**, z tym samym available_at co observed sales.
W bieżącej polityce zwrot jest najwcześniej następnego dnia, więc net=gross
i return_units=0 przy day close. To zero znanych refundacji, a nie obietnica
braku późniejszych zwrotów: return_data_complete=false dla niedojrzałej sprzedaży.
Dzień bez zakupów ma kompletne zerowe zwroty. Missing pozostaje pusty.

Kohorty history mają cutoff o północy UTC po end_date. Kohorty return_tail
mają cutoff 39 dni później: maksymalne okno 37 + opóźnienie 2. Wszystkie
zakupy, również bez zwrotów, są wtedy dojrzałe. Dojrzałość history zależy od
każdej sprzedaży i jej policy deadline + opóźnienie, nie od obecności zwrotu.
Net oznacza gross minus dostępne refundacje, final dopiero po dojrzeniu.

Nie przedłużamy aktywnego panelu sprzedaży ani lifecycle produktu na ogon.
Zwrot może nastąpić po discontinue i nadal rozlicza konkretny wcześniejszy zakup.
Daty zwrotów nie są przycinane do end_date. Legacy returns.csv w profilach AI
jest wyłącznie projekcją zdarzeń dostępnych w history cutoffie; refunded jest
mapowane na dotychczasowy status received. Pełny ogon pozostaje w return_events.

Manifest opisuje osobno watermarks `return_events`,
`daily_return_cohorts.history` i `.return_tail`. Complete_through kohort
oznacza pokryte dni sprzedaży, a dojrzałość refundacji jest flagą każdego wiersza.
Watermark events potwierdza syntetyczną kompletność zdarzeń do end_date + 37 dni,
przy cutoffie uwzględniającym kolejne dwa dni ingestii. Legacy watermarks
pozostają bez ogólnej gwarancji kompletności.

## Bramki i użycie

Siedem hard gates obejmuje schema/PK, polityki okien, chronologię zamówienia
i sprzedaży, konkretne referencje oraz okno/dostępność zwrotu, skumulowaną ilość
i refundacje, dokładne rozliczenia obu snapshotów oraz pełną dojrzałość ogona.
Generacja, feature builder i odczyt manifestu odtwarzają kontrole i JSON/MD;
przeliczenie checksumów nie omija bramek. Return report kwalifikuje zwroty,
bez certyfikowania całego źródła do dalszych etapów AI.

Cechy AI 3.0 nadal mają target observed_sales_units i nie przyjmują revenue,
refundacji ani danych przyszłego ogona. Source 2.0–2.3 i ich feature IDs/parent
pozostają czytelne bez zmiany historycznych polityk. Forecasting, anomaly,
stockout i replay pozostają not_ready; inventory_ready=false. Przed AI 03
pozostaje izolacja truth i końcowy odbiór źródła DATA-05.
