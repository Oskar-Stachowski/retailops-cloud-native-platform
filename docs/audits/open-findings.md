# Otwarte ustalenia audytowe

Przegląd kodu: **27.09.2026**, baza `4da25cba4acd721ce88cb5c07ac7bec23cc8f0f4`.
Poniżej są wyłącznie otwarte problemy potwierdzone w źródłach lub reprodukcji.
[Audyt przygotowań AI](../evidence/pre-ai-00/2026-09-27-readiness.md) rozdziela
nowe testy, przegląd kodu i wcześniej wykonane próby CI. Pozwala rozpocząć AI 00;
nie potwierdza gotowości wszystkich dalszych etapów ani wdrożenia produkcyjnego.

**P1** oznacza ryzyko utraty danych, naruszenia granicy dostępu lub niewiarygodnej
oceny modelu. **P2** oznacza problem odtwarzalności, izolacji lub diagnostyki.
Priorytet dotyczy wskazanego zastosowania, a nie deklaracji gotowości produkcyjnej.

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
Warunek odbioru historycznych danych i forecastingu w AI 02–04, bez blokowania AI 00.

## Runtime i bezpieczeństwo

### OPS-03 · P1 · Consumer zatwierdza offset także po błędzie przetwarzania

**Dowód:** `_handle_message` w
[runnerze consumera](../../services/api/app/services/realtime_consumer_runner.py)
wywołuje `commit` w `finally`, także po błędzie dekodowania lub obsługi.
[Obsługa zdarzenia](../../services/api/app/services/realtime_consumer.py) może
zwrócić `failed_dead_lettered`; próba zapisania błędu w DB również może się nie
powieść. Kod nie wymaga trwałego zachowania błędnej wiadomości przed commitem.
Może to pominąć zdarzenie bez możliwości automatycznego ponowienia.

**Kryterium zamknięcia:** commit dopiero po trwałym sukcesie albo potwierdzonym
zapisie do mechanizmu odtwarzania błędów. Testy rzeczywistego brokera obejmują
błędny payload, awarię DB/handlera, restart, ponowienie i deduplikację; wykazują
brak utraty zdarzenia.

### OPS-04 · P1 · Parametr `dbname` w URL omija izolację bazy testu seeda

**Dowód:** fixture w
[test_seed_data.py](../../services/api/tests/test_seed_data.py) zastępuje
ścieżkę URL losową nazwą bazy, ale zachowuje query. Dla
`postgresql://demo:placeholder@127.0.0.1/retailops?dbname=retailops`
Psycopg i SQLAlchemy nadal wybierają `retailops`, także po zmianie ścieżki
na `/retailops_seed_test_probe`. Potwierdzono to bez połączenia z DB.
Fixture tworzy osobną bazę, ale migracje i
[seed z TRUNCATE](../../services/api/scripts/seed_demo_data.py) mogą trafić
do bazy źródłowej. Katalog danych generatora pozostaje tymczasowy.

**Kryterium zamknięcia:** znormalizowane parametry połączenia nie pozwalają
query nadpisać izolowanej ani administracyjnej nazwy bazy; przed zapisem
sprawdzana jest rzeczywista nazwa bazy. Regresje obejmują zwykły URL,
`dbname` w query, powtórzone i kodowane parametry oraz sprzątanie po błędzie.
Do poprawy przed kolejnym testem seeda na serwerze z wartościowymi danymi;
AI 00 można prowadzić bez uruchamiania tego testu na takiej bazie.

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

**Kryterium zamknięcia:** jeden wersjonowany kontrakt określa tematy, typy,
wymagane pola i regułę wyznaczania tematu. Generator, inicjalizacja brokera,
consumer oraz testy walidują zgodność z nim. Zmiana zachowuje świadomie wybraną
kompatybilność; test wykrywa rozbieżności mapowania i pól.
