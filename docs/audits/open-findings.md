# Otwarte ustalenia audytowe

Przegląd kodu: **27.09.2026**, baza `d7e8725bfb517595d2cefda4d6011f2db70b2aed`.
Poniżej są wyłącznie problemy potwierdzone w źródłach. Ocena ich zakresu
opiera się na przeglądzie statycznym; test tożsamości RF nie weryfikuje jakości
prognoz ani kont zewnętrznych.

**P1** oznacza ryzyko utraty danych, naruszenia granicy dostępu lub niewiarygodnej
oceny modelu. **P2** oznacza problem odtwarzalności, izolacji lub diagnostyki.
Priorytet dotyczy wskazanego zastosowania, a nie deklaracji gotowości produkcyjnej.

## ML — do poprawy przed następną oceną modelu

### ML-02 · P1 · Protokół nie weryfikuje prognozy całego horyzontu z jednego origin

**Dowód:** `build_supervised_examples` w
[modelu RF](../../ml/models/random_forest_forecast.py) przekazuje wszystkie
wcześniejsze wiersze serii, także rzeczywiste wyniki wcześniejszych dni holdoutu.
`horizon_days` jest parametrem konfiguracji, lecz nie steruje tym treningiem ani
oceną. Kod wykonuje ocenę kroczącą, a nie zamrożoną prognozę siedmiodniową.
`lag_7` oznacza siódmą wcześniejszą obserwację, a `window_days` liczbę wierszy;
baseline w tym samym pliku filtruje okno po datach. Przy brakujących dniach są
to różne zakresy historii. [Generator cech](../../ml/features/demand_forecast.py)
tworzy wiersze z agregatów sprzedaży, bez pełnego kalendarza serii.
Nieobecnych kombinacji nie da się jeszcze sklasyfikować jako brak danych,
zamknięty sklep lub nieaktywny asortyment.

**Kryterium zamknięcia:** oddzielnie nazwane i przetestowane protokoły dla
stałego origin i oceny kroczącej; model i baseline mają tę samą granicę wiedzy
oraz zbiór ocenianych rekordów. Lagi i okna odnoszą się do dat kalendarzowych,
z jawnym rozróżnieniem brakujących danych i zerowej sprzedaży. Raport zawiera
origin, horyzont, pokrycie, pominięcia, chronologiczne okna walidacji i odłożony
test, którego nie używa się do strojenia.

### ML-03 · P1 · Nieokreślone metryki są raportowane jako zero

**Dowód:** `calculate_prediction_metrics` i `_safe_percentage_error` w
[modelu RF](../../ml/models/random_forest_forecast.py) oraz `calculate_metrics`
w [ocenie baseline](../../ml/evaluation/baseline_report.py) zwracają WAPE równe
zero przy zerowej sumie actuals. MAPE przypisuje zerowy błąd procentowy rekordom
z actual równym zero i uwzględnia je w średniej. Dodatnia błędna prognoza na
samych zerach może więc otrzymać WAPE i MAPE równe zero.

**Kryterium zamknięcia:** WAPE przy zerowym mianowniku ma `null` i status
`not_evaluable`; MAPE obejmuje jawnie określone dodatnie actuals i podaje pokrycie.
Raport zachowuje MAE i nadmiarową prognozę na zerach. Pusty zbiór, nieprawidłowe
wartości i brak ocenialnej metryki nie pozwalają przejść bramki jakości.
Test obejmuje m.in. actual `[0]`, prediction `[100]`.

### ML-04 · P1 · Status modelu nie wynika z pełnej polityki dopuszczenia

**Dowód:** `model_status_from_metrics` w
[modelu RF](../../ml/models/random_forest_forecast.py) nadaje `candidate` po
dowolnej poprawie WAPE względem baseline. Nie sprawdza pokrycia, stabilności,
segmentów, odtwarzalności ani ważności protokołu. W
[rejestrze metadanych](../../ml/metadata/model_registry.py) status, także
`approved`, pochodzi z argumentu użytkownika; `_validate_status` sprawdza
wyłącznie przynależność do listy dozwolonych nazw.

**Kryterium zamknięcia:** wersjonowana polityka ustalona przed oceną zapisuje
wynik i uzasadnienie każdego warunku. Progi muszą wynikać z uzgodnionego kontraktu,
nie z dopasowania do uzyskanego wyniku. Ścieżka dopuszczania weryfikuje dowody
i blokuje ręczne obejście decyzji. `candidate` oznacza zgodę na dalszą lokalną
walidację; poprawne `rejected` jest pełnoprawnym wynikiem eksperymentu.

### ML-05 · P1 · Batch, metadata i metryki nie używają ocenionego artefaktu RF

**Dowód:** [batch inference](../../ml/inference/batch_forecast.py) wywołuje
`build_baseline_forecasts`, [metadata registry](../../ml/metadata/model_registry.py)
ponownie uruchamia trening i ocenę baseline, a
[raport metryk](../../ml/observability/model_performance_metrics.py) uruchamia
tę samą ścieżkę batch. Żaden z tych kroków nie odczytuje zapisanego
`random_forest_model.joblib`. Uruchomienie wszystkich komend `make ml-*` nie
potwierdza użycia jednego modelu od treningu do prognoz i monitoringu.

**Kryterium zamknięcia:** lokalna ścieżka odczytuje dokładnie oceniony artefakt,
bez niejawnego ponownego treningu ani przełączenia na baseline. Model, dataset,
eksperyment, prognozy i metryki mają wspólną zweryfikowaną tożsamość. Test
porównuje prognozy przed zapisem i po odczycie oraz odrzuca niezgodny artefakt.

## Runtime i bezpieczeństwo

### OPS-01 · P1 · Zwykłe zatrzymanie Compose usuwa wolumeny

**Dowód:** target `compose-down` w [Makefile](../../Makefile) wykonuje
`docker compose down -v --remove-orphans`. Usuwa więc dane wolumenów danego
projektu, mimo nazwy sugerującej samo zatrzymanie.

**Kryterium zamknięcia:** zwykłe `compose-down` zachowuje wolumeny; usuwanie
danych ma osobny, jednoznaczny target resetu. Zwykłe ponowne uruchomienie nie
seeduje ponownie bazy. Weryfikacja zapisuje rekord, zatrzymuje i uruchamia ten
sam projekt oraz potwierdza zachowanie rekordu. Do czasu poprawki zatrzymuj
stack przez `docker compose --profile dev --profile observability stop`;
[instrukcja lokalna](../guides/local-development.md) opisuje wznowienie bez seeda.

### OPS-02 · P1 · Demo auth jest połączone z domyślnym nasłuchem na wszystkich interfejsach

**Dowód:** [model użytkowników](../../services/api/app/auth/roles.py) wybiera
tożsamość na podstawie `user_id`, a bez niego `platform-admin`.
[Compose](../../docker-compose.yml) publikuje porty API i frontendu z
`HOST_BIND` domyślnie równym `0.0.0.0`. Dostępny klient może wybrać rolę
administratora; to nie jest uwierzytelnienie rzeczywistego użytkownika.

**Kryterium zamknięcia dla lokalnego demo:** domyślny bind do loopback i
technicznie egzekwowana granica lokalnego dostępu. Przed udostępnieniem innym
użytkownikom wymagane jest rzeczywiste uwierzytelnienie, walidacja tożsamości,
domyślna odmowa oraz testy 401/403 i dozwolonych operacji. Do czasu poprawki
lokalne uruchomienie wymaga `HOST_BIND=127.0.0.1`.

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

### OPS-04 · P2 · Test seeda zapisuje do danych projektu

**Dowód:** automatyczna fixture w
[test_seed_data.py](../../services/api/tests/test_seed_data.py) uruchamia
generator bez `--output-dir`, a potem odczytuje `data/demo` i seeduje wskazane
`DATABASE_URL`. [Generator](../../data/generator/main.py) używa domyślnie
śledzonego katalogu `data/demo`. Test nie izoluje wyjścia generatora.

**Kryterium zamknięcia:** generator pracuje w katalogu tymczasowym, seed
korzysta z tego samego katalogu i izolowanej bazy. Powtórne uruchomienie oraz
błąd testu nie zmieniają śledzonych danych ani bazy deweloperskiej.

### OPS-05 · P2 · Diagnostyka testów może ujawnić hasło do bazy

**Dowód:** `_db_unavailable_reason` w
[conftest.py](../../services/api/tests/conftest.py) umieszcza pełne
`DATABASE_URL` oraz tekst wyjątku w komunikacie skip/fail. URL może zawierać hasło.

**Kryterium zamknięcia:** komunikat podaje bezpieczny powód niedostępności bez
sekretów; test negatywny potwierdza brak hasła i pełnego URL w logach oraz raporcie.

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
