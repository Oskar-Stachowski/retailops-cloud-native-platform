# Otwarte ustalenia audytowe

Pomiary bazowe: **27.09.2026**, baza `cbf28b2a66e7e5f205cf73d9bfe620c491e22d93`.
Aktualizacja otwartego zakresu: **28.09.2026**.
Poniżej są wyłącznie otwarte problemy potwierdzone w źródłach lub reprodukcji.
[Audyt AI 00](../evidence/ai/00/README.md) rozdziela pomiary, 138 testów,
przegląd statyczny i odczyt CI. Pozwala rozpocząć AI 01;
nie potwierdza gotowości wszystkich dalszych etapów ani wdrożenia produkcyjnego.
Kolejność pracy i pierwsze małe PR-y: [backlog AI](../plans/ai/backlog.md).

**P1** oznacza ryzyko utraty danych, naruszenia granicy dostępu lub niewiarygodnej
oceny modelu. **P2** oznacza problem odtwarzalności, izolacji lub diagnostyki.
Priorytet dotyczy wskazanego zastosowania, a nie deklaracji gotowości produkcyjnej.

## Źródło danych AI

Pomiary DATA-01–06: [source-measurements.json](../evidence/ai/00/source-measurements.json),
profil `small`, 90 dni, 100 produktów, seed 42. Nie są pomiarami danych rzeczywistych.

### DATA-03 · P1 · Zwroty i pełne bramki chronologii wymagają poprawy

**Dowód:** [generate_profile_returns](../../data/generator/profile_engine.py)
wyznacza returned_at względem końca całej historii i indeksu pozycji, bez okna
własnej sprzedaży, kategorii i kanału. Źródłowy panel nie zatwierdza jeszcze
net revenue ani return units. Nie ma pełnej bramki ordered/sold/returned ani
skumulowanych zwrotów dla nowego eksportu AI.

**Kryterium zamknięcia — AI 02:** wersjonowana polityka zwrotu konkretnej pozycji,
category/channel window, ilość częściowa, skumulowany zwrot ≤ zakup,
gross/net revenue i osobny tail. Ordered ≤ sold ≤ returned oraz availability
muszą być egzekwowane także na celowo błędnych danych, z nonzero exit.
Zdarzenia po watermark nie wchodzą do wcześniejszego snapshotu.

### DATA-05 · P1 · Pełna izolacja truth i odbiór źródła pozostają otwarte

**Dowód:** products/stores nadal są sklasyfikowane jako mixed_fact_and_simulation_truth:
demand_weight/elasticity/return_rate i traffic/promo_sensitivity są w legacy
adapterach. Builder generuje pełne źródło wraz z truth przed upstream gates;
sam moduł cech przyjmuje wyłącznie jawne fakty, ale nie dowodzi izolacji procesu
ani runtime. Źródło deklaruje forecasting/anomaly/stockout/replay not_ready.

**Kryterium zamknięcia — AI 02, etykiety w 07:** zakończyć rozdzielenie
operational/truth/labels oraz kontrolę dostępu procesu/runtime. Domknąć
quality/realism/readiness per use case, polityki i negatywne przypadki pełnego
źródła, z JSON/MD evidence oraz niezerowym exit przy wymaganym błędzie.
Zachować istniejące kontrole i odrzucać truth jako wejście features/runtime.

### DATA-06 · P1 · Snapshoty wielokrotnie otwierają inventory bez uzgodnionego ledgeru

**Dowód:** 1300 `initial_stock` dla 300 par produkt/magazyn, 1000 nadmiarowych otwarć.
Movement sprzedaży dobiera magazyn przez indeks modulo, bez historycznego fulfillment
mapping. Kod: [inventory i stock movements](../../data/generator/profile_engine.py).

**Kryterium zamknięcia — AI 06, przed 08:** jedno otwarcie, wersjonowane mapowanie
selling/stock location, uzgodnienie bilansu ruchów/sprzedaży/dostaw/zwrotów,
availability snapshotów i testy braku/przyszłego zapasu. Dopiero wtedy labels stockout.
Nie blokuje forecast-only AI 04–05, gdzie inventory features są pominięte.

## ML i historia danych

### ML-07 · P2 · Dzienny agregat nie zachowuje wcześniejszych wersji historii

**Dowód:** `_build_aggregates` w
[generatorze cech](../../ml/features/demand_forecast.py) sumuje wszystkie
sprzedaże dnia i zapisuje maksymalny czas dostępności. Dodanie spóźnionej
sprzedaży do historycznego dnia przesuwa dostępność całego agregatu. Przy
odtwarzaniu wcześniejszego origin znika także poprzednio znana część sprzedaży;
reprodukcja zmienia `lag_1_units` z 3 na 0 i wskaźnik dostępności z 1 na 0.

To ograniczenie przyszłego importu i odtwarzania historii, nie wykazany błąd
zapisanej oceny RF: obecny generator syntetyczny dostarcza sprzedaż tego samego
dnia, a panel ocenionego przebiegu nie zawiera dostępności z późniejszego dnia.

**Kryterium zamknięcia:** wersjonowane agregaty albo agregacja według stanu
znanego w origin. Dodanie późniejszej sprzedaży lub korekty nie zmienia cech
ani prognoz wcześniejszego origin. Brak potrzebnej historii ma jawny status.
Warunek odbioru historycznych danych i forecastingu w AI 02–04, bez blokowania AI 01.

## Runtime i bezpieczeństwo

### OPS-03 · P1 · Consumer zatwierdza offset także po błędzie przetwarzania

**Dowód:** `_handle_message` w
[runnerze consumera](../../services/api/app/services/realtime_consumer_runner.py)
wywołuje `commit` w `finally`, także po błędzie dekodowania lub obsługi.
[Obsługa zdarzenia](../../services/api/app/services/realtime_consumer.py) może
zwrócić `failed_dead_lettered`; próba zapisania błędu w DB również może się nie
powieść. Kod nie wymaga trwałego zachowania błędnej wiadomości przed commitem.
Może to pominąć zdarzenie bez możliwości automatycznego ponowienia.
[Próby AI 00](../evidence/ai/00/contracts.json) na prawdziwym runnerze z mockami
potwierdziły commit przy invalid JSON oraz jednoczesnej awarii DB/kwarantanny.
Nie są testem rzeczywistego brokera ani dowodem trwałości.

**Kryterium zamknięcia:** commit dopiero po trwałym sukcesie albo potwierdzonym
zapisie do mechanizmu odtwarzania błędów. Testy rzeczywistego brokera obejmują
błędny payload, awarię DB/handlera, restart, ponowienie i deduplikację; wykazują
brak utraty zdarzenia.

### OPS-06 · P2 · Zależności builda i workflow są wskazywane ruchomymi tagami

**Dowód:** [Dockerfile API](../../services/api/Dockerfile) i
[Dockerfile frontendu](../../frontend/Dockerfile) używają tagów bazowych bez
digestów. Zewnętrzne actions, także w
[workflow wydania](../../.github/workflows/release.yml), są wskazywane tagami
takimi jak `actions/checkout@v6`, nie pełnym SHA. Identyczny commit repozytorium
nie identyfikuje zatem jednoznacznie wszystkich wejść przyszłego builda.

**Kryterium zamknięcia:** pełne SHA dla zewnętrznych actions oraz digesty bazowych
obrazów, aktualizowane kontrolowanym PR z walidacją. Dowód wydania zapisuje
rozwiązane tożsamości wejść i wynikowych artefaktów.

### OPS-07 · P2 · Kontrakt zdarzeń JSON odbiega od generatora i consumera

**Dowód:** [kontrakt JSON](../../events/contracts/retailops-realtime-events.v1.contract.json)
deklaruje tematy `retailops.orders.v1` i `retailops.ml.v1`, pomija typy
`return_completed` oraz `replenishment_completed` i wymaga pola `topic`.
[Generator](../../data/generator/realtime.py) i
[consumer](../../services/api/app/services/realtime_consumer.py) używają dla
tych przepływów `retailops.sales.v1` i `retailops.intelligence.v1` oraz obsługują
oba dodatkowe typy; consumer nie wymaga `topic` w envelope. Konsument kierujący
się plikiem kontraktu może otrzymać inny zakres niż działający runtime.
[AI 00](../evidence/ai/00/contracts.json) odtworzył 49 856 zdarzeń i potwierdził
zgodność generatora z topic init/consumerem, ale parser akceptuje brak/błędny temat,
wersję `999` i pusty payload. W dwóch różnych snapshotach 8501 event IDs ma różną
treść: tożsamość nie obejmuje wersji snapshotu/payloadu.

**Kryterium zamknięcia:** jeden wersjonowany kontrakt określa tematy, typy,
wymagane pola i regułę wyznaczania tematu. Generator, inicjalizacja brokera,
consumer oraz testy walidują zgodność z nim. Zmiana zachowuje świadomie wybraną
kompatybilność; test wykrywa rozbieżności mapowania i pól.
Walidować payload/version/topic transportu i rozdzielić replay tego samego zdarzenia
od nowej wersji danych. Etap AI 10 musi zachować legacy v1 i osobny kontrakt
`intelligence.v2`; pełne domain projectors są nową funkcją z planu, nie istniejącą
gwarancją konsumenta metryk.
