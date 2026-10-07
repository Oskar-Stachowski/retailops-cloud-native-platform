# Native anomaly i stockout — read API oraz odzyskiwanie

Status: przyrost AI 10; pełny etap pozostaje `in_progress`. Wspólny topic
`retailops.intelligence.v2` zachowuje forecast i dodaje dokładne publiczne
payloady anomaly/physical stockout AI 07/08. Sugestie mają osobny fixture contract.

## Migracja i pochodzenie

1. Porównaj wszystkie SHA w `services/api/app/contracts/intelligence-v2/upstream.json`
   z dokładnym przypiętym commitem repo AI. Payloadów nie edytuj ręcznie.
2. Na własnej bazie wykonaj `alembic upgrade head` do `a10f0c7e0600`.
   Migracja dodaje `ai_model_results`, `ai_model_intelligence_inbox` i nullable
   `model_result_id` transport receipt. Wcześniejsze migrations są niezmienne.
3. Uruchom istniejący fenced checkpoint runner w osobnej grupie v2. Projekcja,
   inbox, receipt i cursor są jedną transakcją. ACK jest po jej zatwierdzeniu.
   Broker/redelivery nie są dowodem nowego model runa.

## Prywatne odczyty

4. Poza Git przygotuj plik `0600` należący do procesu API i ustaw
   `RETAILOPS_INTELLIGENCE_MODEL_ACCESS_POLICY`. Polityka ma version
   `retailops-model-intelligence-access-1.0`, listę `principals`, a każdy
   principal ma unikalne `principal_id`, `credential_sha256`, `capabilities`.
   Credential nie znajduje się w polityce w postaci jawnej.
5. Dla `anomaly:read` nadaj `anomaly_scope`: `product_ids`,
   `selling_location_ids`, `channels`, `currencies`, `release_ids`.
   Dla `stockout:read` nadaj `stockout_scope`: `product_ids`,
   `stock_location_ids`, `release_ids`. Scope nieudzielonej capability jest
   `null`. Grant sprzedażowy nie udziela dostępu do fizycznego zapasu.
6. Odczytuj wyłącznie osobistym Bearer credential:

   | Zasób | Lista | Szczegół |
   | --- | --- | --- |
   | anomaly | `/intelligence/v2/anomalies` | `/{anomaly_id}` |
   | stockout ML | `/intelligence/v2/stockout-risks` | `/{risk_id}` |

   Wspólne filtry to product/release/run, limit `1..100`, offset `0..10000`
   i `view_sha256`. Anomaly dodatkowo filtruje selling location/channel/currency;
   stockout filtruje physical stock location. Unknown/repeated query to 422,
   obcy filtr 403, obcy lub brakujący literal result ID 404. Offset >0 wymaga
   niezmienionego hash widoku. Zmieniony view/grant daje 409. Globalny census
   ograniczono do 10000 wyników; większy scope wymaga zawężenia odczytu.
7. W istniejącej stronie Anomalies podłącz credential oddzielnie do panelu
   anomaly lub stockout. Tabela zachowuje rzeczywiste ziarno i statusy.
   Stockout bez score ma `Unavailable`, a nie zero probability. Lineage
   zachowuje native ID/model/release/run oraz rodziców danych. Historyczne
   odczyty nie deklarują nowego aktywnego modelu.

Credential pozostaje w pamięci karty najwyżej pięć minut. Disconnect, ukrycie
karty i zmiana demo usera czyszczą odczyty oraz anulują pending requests.
Serwer wczytuje grant przy każdym żądaniu; podmiana SHA odwołuje credential
bez restartu. `user_id` demo nie zwiększa praw. Każda odpowiedź ma
`Cache-Control: no-store` i `Vary: Authorization`.

## Świeżość, replay i rollback

Original payload i ID są niezmienne. `freshness` response jest osobną oceną
w chwili odczytu. Dawny anomaly origin przekraczający siedem dni oraz stockout
as-of przekraczający dobę są stale; wynik z przyszłości jest unknown. Dostęp
do Bedrock nie jest potrzebny do tych odczytów.

Przed SQL commit awaria pozostawia broker offset bez ACK. Po SQL commit i
przed ACK restart reużywa receipt bez drugiej projekcji. Poison zachowuje raw
payload/transport w kwarantannie; konflikt native ID nie nadpisuje wyniku.
Naprawiony replay wykorzystuje ten sam original ID i semantyczny partition key.
Stosuj istniejący [runbook zdarzeń](realtime-recovery.md).

UPDATE/DELETE model history i inbox są zabronione w SQL. Downgrade z niepustą
projekcją jest odmawiany. Application rollback zachowuje expanded schema
i wszystkie dane, zgodnie z [procedurą rollback](application-rollback.md).
Compose i Kubernetes drills zasiewają oba model payloady, inboxy i receipts,
aby porównanie fingerprintów obejmowało również niepuste nowe tabele.

## Dowody

Lokalne testy kontraktów/grantów/regresji oraz frontend lint/55 tests/build
przechodzą. Rzeczywisty PostgreSQL/broker jest wymagany w API CI przez
`test_intelligence_model_durability.py`: native-shaped fixtures, duplikaty,
SQL failure, SIGKILL przed ACK, poison, ID collision, history ordering,
scope i immutability/downgrade refusal. Built browser drill w istniejącym
frontend CI sprawdza SQL/API, literal IDs, 50/20 pagination, original lineage,
odwołanie credential i niezależność od późnej odpowiedzi legacy dashboard.

Przykłady z `model-fixtures.json` oraz browser/rollback fixtures sprawdzają
mechanikę. Nie kwalifikują modeli i nie zamykają pełnego temporalnego E2E.
Pełny Source capture/snapshot/replay oraz trzy rzeczywiste model runs wymagają
osobnego odbioru zgodnego z [planem AI 10](../plans/ai/etapy/10-integracja-retailops.md).

## Odbiór oryginalnych wyników na runnerze AI10

`tests/test_native_intelligence_output_durability.py` wymaga pakietu z
rzeczywistego acceptora AI08 uruchomionego na tym samym runnerze AI10.
`AI10_NATIVE_STOCKOUT_OUTPUT` wskazuje `accepted-model`,
`AI10_NATIVE_PRODUCER_COMMIT` wiąże oryginalny commit producenta, a
`AI10_NATIVE_READ_REPORT` wskazuje plik raportu. Dedykowany workflow ustawia
`REQUIRE_AI10_NATIVE_MODEL_READ=1` oraz `REQUIRE_BROKER_TESTS=1`, wymagając
rzeczywistego brokera i osobnej testowej bazy; lokalnie Docker
pozostaje wyłączony. Brak pakietu nigdy nie wybiera fixture.

Odbiór porównuje pełny oryginalny output, census SHA-256 i każdy native
payload/ID. Dwukrotna wysyłka oryginalnych bytes daje jeden wynik SQL i
odpowiednie checkpoints/ACK. Uwierzytelniony odczyt TCP sprawdza każdy
oryginalny `risk_id`, payload oraz brak eskalacji przez query/demo user.
Ten test obejmuje przekazanie plikowe committed outbox do Source; nie
poświadcza wysyłki z oryginalnej bazy AI ani UI dla tych wyników. Oddzielny
istniejący UI drill pozostaje dowodem mechaniki ekranów na oznaczonych fixture.

## Odbiór oryginalnych wyników przez broker/API/UI

Dedykowany workflow AI10 przypina dokładny commit odbiorcy Source i SHA jego
plików. `REQUIRE_AI10_NATIVE_MODEL_READ=1` wymaga artefaktu bieżącego producer
commitu i GitHub run ID; brak pakietu przerywa test. Stockout używa pełnego
oryginalnego outputu/census po cold worker. Anomaly wymaga pełnego OCI,
registry, scoped HTTP oraz restartu po SIGKILL, a ponadto dokładnych bajtów
zamrożonego primary modelu z zaakceptowanego AI07. Schematowy anomaly fixture
ma literalne `passed_at_publication`, lecz nie zawiera tych dowodów wykonania.

Każdy event jest wysłany dwukrotnie przez rzeczywisty broker. Consumer
przetwarza bounded partie po najwyżej 100 receipts, z kolejnymi claims;
raport wymaga pełnego census projekcji, duplikatów i wektora ACK obu partycji.
Wszystkie oryginalne ID są odczytywane przez owned TCP API z prywatnym grantem.
`REQUIRE_AI10_NATIVE_BROWSER=1` dodatkowo wymaga zbudowanego frontendu oraz
Chromium. Dedicated Playwright project `native-intelligence-chromium` porównuje
cały zestaw niezmienionych payloadów, wszystkie strony istniejącego panelu,
native grain, status, literalny ID, lineage oraz policy revocation bez restartu.
Private credentials nie trafiają do storage, report ani uploadów.

Do wyboru anomaly służy `AI10_NATIVE_MODEL_KIND=anomaly_detected` oraz
`AI10_NATIVE_ANOMALY_OUTPUT`; domyślny stockout używa
`AI10_NATIVE_STOCKOUT_OUTPUT`. `AI10_NATIVE_PRODUCER_COMMIT` i
`AI10_NATIVE_READ_REPORT` ustala przypięty caller CI. Ogólne CI bez artefaktu
nie uruchamia tego dedykowanego odbioru. To file handoff prawdziwego committed
outboxu; raport nie poświadcza jeszcze wysyłki z oryginalnej bazy AI.
