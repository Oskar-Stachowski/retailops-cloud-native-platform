# AI 10 — integracja wyników w RetailOps

Aktualizacja: 2026-10-07. **Status: ready — odbiór integracji AI 10.**
Pełny oryginalny [V12](v12-22de575.json), run `37665627162` na AI `22de575`,
zaliczył 273 testy granic i rzeczywisty Source E2E: 56 wyników, 56 ACK oryginalnego
publishera AI SQL, 56 projekcji i 56 duplikatów, pełny TCP API oraz dwie strony
istniejącego built UI z live revocation. Frozen Source `1a7f558` zachowuje
102 dni historii, 43 tabele i osobne 14 dni planów bez truth.
[Stockout](stockout-64a4c71.json) ma 40 wyników/ACK/projekcji/duplikatów,
a [anomaly](anomaly-64a4c71.json) 1232 oraz 25 stron UI. Niezależne parsery
Source sprawdziły komplet payloadów i lineage wszystkich trzech ścieżek.

V12 działa wyłącznie w `retailops-demand-forecast-v12-development`.
Oryginalne quality `not_ready`, trzy niezaliczone MSE gates i decyzja właściciela
pozostają zachowane. UI pokazuje ostrzeżenie development; nie ma refitów,
przekwalifikowania jakości ani deploymentu produkcyjnego.

Kod wcześniejszych jedenastu przyrostów Source jest już zawarty w main.
[Pełny Source main `467f990`](source-code-main-ci.json) ma 30/30 success,
[nowszy `b723489`](source-b723489-main-ci.json) 21 success i 4 celowe skipped
zgodnie z niezmienionym wykrywaniem obszarów. [AI main `b0e2de`](ai-b0-main-ci.json)
ma 17/17 success. [Zgodność native runtime](native-runtime-main-compatibility.json)
wiąże odebrane commity z aktualną integracją; całego katalogu AI src nie uznaje
za identyczny. Poprawkę launchera i końcowe dowody publikuje
[AI #38](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/pull/38).
Publikacja tego rekordu wymaga normalnego protected merge i zielonego Required CI
jego dokładnych headów oraz wynikowych main; dowodem tej bramki są checks PR-ów
oraz merge commitów w GitHub, niezależnie od historycznych receipts.

## Zakres

RetailOps utrwala forecast, anomaly i stockout w osobnych read models,
z oryginalnym payloadem, native ID, grain, source/model/run/dataset lineage
i odczytywaną świeżością. Są dostępne w istniejących panelach Forecasts/Anomalies;
legacy forecast okresowy i heurystyczne inventory risk zachowują znaczenie.
Osobisty grant ustala serwer i nie dziedziczy demo admina. Credential UI jest
przechowywany tylko w pamięci, a odwołanie grantu usuwa dane widoku.

| Ścieżka | Dowód i granica |
| --- | --- |
| Snapshot | [Source bundles](../../../runbooks/source-bundles.md): immutable komplet plików, typed import, SHA i osobny service grant |
| REST | [Source reads v2](../../../runbooks/source-reads-v2.md): bounded live odczyty rzeczywistych legacy zasobów, OpenAPI, 50/100 pagination i auth; pełne sales grain i ogólny snapshot/handoff pozostają unsupported |
| Stream | [Source observation capture](../../../runbooks/source-observation-capture.md): operational SQL outbox, TLS/SCRAM, pełny prefix, osobny AI SQL/ACK, overlap i korekta 4 → 7; [receipt](source-sql-handoff.json) |
| Stockout | **Passed**: frozen model, oryginalny AI SQL publisher i 40 ACK, Source SQL/API/built UI, 40 duplikatów i ACK `[34,46]`; [receipt](stockout-original-sql.json) |
| Anomaly | **Passed**: oryginalny AI07, OCI/registry/SIGKILL, oryginalny publisher AI SQL i 1232 ACK, 1232 wyników/1232 duplikatów, API oraz 25 stron built UI; [receipt](anomaly-original-sql.json) |
| V12 | **Passed**: [pełny oryginalny receipt](v12-22de575.json), 56 wyników/ACK/projekcji/duplikatów, ACK `[70,42]`, pełny TCP API i 2 strony UI; oryginalna jakość `not_ready`, wyłącznie zaakceptowany development |
| Sugestie | [Jawny fixture i human approval](../../../runbooks/intelligence-suggestion-ui.md) w zakresie AI10; rzeczywisty producent należy do AI12 |

Ścieżka streamu obejmuje `daily_demand_versions`, a jej obserwacje do testu
protokołu są jawnie wygenerowane. Pełny immutable bundle 43 tabel nie dostaje
fikcyjnego wektora brokera. Modelowe wejścia temporalne, kwalifikacje i polityki
freshness zachowują własne oryginalne lineage; odbiór integracji nie tworzy
nowego eksperymentu jakości porównującego trzy modele.
Pełne native grain, record versions i availability dostarcza osobny
wersjonowany immutable bundle. Ograniczone strony REST nie rozszerzają
deklarowanych capabilities źródła.

## Odtwarzanie i awarie

Własność danych i diagram obu niezależnych baz opisuje
[AI10 acceptance](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/blob/main/docs/ai10-acceptance.md).
Source odpowiada za fakty operacyjne, eksporty, read models i istniejący UI;
AI za własne importy, registry, obliczenia i outbox. Broker przenosi zdarzenia,
a osobne transakcje SQL i grants wyznaczają granice trwałości.

1. Przypnij dokładne commity obu repo i bytes/schema/registry. Wykonaj jawne
   migracje na osobnych bazach AI/Source oraz użyj oddzielnych prywatnych grantów.
2. Snapshot i REST odtwarzaj zgodnie z podlinkowanymi runbookami. Świeżość
   pochodzi z biznesowej dostępności, a nie czasu pobrania HTTP. Brak izolacji
   historii oznacza jawny unsupported, bez reklamowania live stron jako snapshotu.
3. W Source observation lane append/publish zapisuje niezmienną wersję i outbox.
   ACK brokera poprzedza zapis receipt w SQL. Capture czyta wszystkie rzeczywiste
   pozycje brokera pod Source SQL authority barrier i nie zapisuje offsetów.
4. W oddzielnym AI SQL facts/raw receipt/checkpoint/quarantine mają jeden commit,
   a broker ACK dotyczy tylko faktycznie odczytanego offsetu. Replay i korekta
   muszą zachować jeden biznesowy efekt. Utrata retencji wymaga nowego resync.
5. Stockout/anomaly/v12 acceptory zachowują oryginalną bazę AI do końca odbioru
   Source. Publisher z tej bazy wysyła pełny census i utrwala rzeczywisty ACK.
   Source wiąże original ACK coordinates i pełne native IDs/payloads z własnym
   checkpoint receipt. Stockout/anomaly dodatkowo sprawdzają SHA wire bytes oraz
   pełny transport fingerprint value/key/headers/timestamp. V12 zachowuje SHA
   oryginalnego eventu w publisher receipt i pełne payloady SQL/API/UI; nie
   poświadcza osobnego bounded reread wszystkich original wire bytes.
6. Wymagaj pełnego odczytu wszystkich oryginalnych ID przez TCP API i built UI,
   paginacji, lineage, 401/403/422 oraz live revocation. Nie zastępuj native outputu
   oznaczonym mechanics fixture. Fixture sugestii jest osobnym dozwolonym zakresem.
7. Testuj SQL failure przed commit bez ACK, SIGKILL po commit, fencing i lukę
   offsetów. Raw poison zachowaj przed ACK; niedostępne SQL/quarantine zatrzymuje
   partycję. Po naprawie uruchom tę samą grupę bez ręcznego pomijania rekordów.
8. Cleanup usuwa tylko własne kontenery/volumes potwierdzone UUID/label oraz
   prywatne pliki. Runnery są jednorazowe; lokalny Docker tej sesji jest wyłączony.

Source udostępnia `make integration-replay-test` i `make integration-failure-test`.
To rzeczywiste testy SQL/brokera na jawnych fixtures mechaniki; pełne native
modele/API/UI wykonują dedykowane workflowy AI10 na własnych runnerach.
[Runbook checkpoints](../../../runbooks/intelligence-checkpoints.md) opisuje ACK,
quarantine i naprawę. [Modele v2](../../../runbooks/intelligence-models-v2.md)
opisują fizyczne i sprzedażowe scope bez eskalacji praw.

## Historia wykonania i publikacja

Pełny odbiór kończy run `37665627162`; wcześniejsze failed próby i diagnostyka
pozostają poniżej jako historia, bez przepisywania ich wyników.


Pełny V12 na AI `64a4c71`, run `37636569401`, zaliczył 262 boundary tests,
pełną oryginalną kwalifikację/cold probes, review/MLflow/registry, actual
intake/cold worker, atomowy rollback i SQL publikację 56 prognoz.
[Końcowy odbiór Source failed](v12-source-consumer-failure.json); failing child
JUnit/log nie zostały zachowane, więc szczegółowa przyczyna jest nieustalona.
[Source diagnostic](v12-reconstructed-source-diagnostic.json), run `37651238268`,
przeszedł pełny rzeczywisty test odbioru tych samych bytes na odtworzonej
bazie fixture. Nie poświadcza oryginalnej bazy ani zamknięcia V12.
Pełny run `37653954039` zaliczył 270 boundary tests i pięć etapów AI,
ale [Source startup failed](v12-source-startup-failure.json) nie wytworzył JUnit.
Kontroler rozwiązywał symlink venv do bazowego interpretera; rzeczywisty
lokalny subprocess reprodukuje utratę środowiska. Dokładny stderr failed child
pozostaje nieznany. [AI #38](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/pull/38)
zachowuje venv entry point i kontroluje prefix/pytest przed długą kwalifikacją.
Wszystkie oryginalne modele, Source test i science/runtime gates pozostają wymagane.

[Stockout](stockout-64a4c71.json) i [anomaly](anomaly-64a4c71.json) w runie
`37636434765` na AI `64a4c71` ponownie przeszły pełne oryginalne SQL
publishery, 40/1232 ACK, wszystkie native payloads w TCP API i built UI.
Zachowują oryginalne kwalifikacje i piny Source, bez refitów.

- [x] Oryginalny Source capture do tego samego brokera i rzeczywistego AI SQL/ACK.
- [x] Native stockout/anomaly w prawdziwym Source API i istniejącym built UI.
- [x] Oryginalny publisher AI SQL stockout w pełnym nowym runtime.
- [x] Oryginalny publisher AI SQL anomaly w pełnym nowym runtime.
- [x] Oryginalny v12 registry/SQL/publisher/Source API/UI na 102 dniach: 56 pełnych wyników.
- [x] Końcowy bounded raport, pełne receipts i powiązanie zakresów CI.
- [x] Kod #28/#100: normalny protected merge i zielone pełne Required CI obu main.
- [x] Końcowe dokumenty i registry ready; ich dostarczenie podlega chronionym PR-om i Required CI dokładnych main.

Pełna bieżąca instrukcja i receipts po stronie AI:
[AI10 acceptance](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/blob/main/docs/ai10-acceptance.md).
Oryginalnych historycznych receipts nie przepisujemy na wynik późniejszych prób.
