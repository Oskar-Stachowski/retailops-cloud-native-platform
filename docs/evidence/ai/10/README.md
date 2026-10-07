# AI 10 — integracja wyników w RetailOps

Aktualizacja: 2026-10-07. **Status: in_progress.** Implementacja jest w
[Source #100](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/pull/100)
i [AI #28](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/pull/28).
AI 07 i AI 08 są odebrane; AI10 zachowuje ich modele i kwalifikacje.
Pełne Required CI Source `cbbf711` ma 30/30 zaliczonych jobów:
[receipt komponentów](source-component-ci.json). Nowszy `4b03664` także zaliczył
30/30 jobów w runie `37617019955`. Nowy head po dołączeniu main AI09
i oba opublikowane main wymagają własnego potwierdzenia.

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
| V12 | [Własny development namespace](../../../runbooks/native-v12-development-acceptance.md), dokładna decyzja właściciela i oryginalna jakość `not_ready`; pełny native runtime na 102 dniach pending |
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
[AI10 acceptance](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/blob/ai/10-ready/docs/ai10-acceptance.md).
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

## Publikacja

Pełny v12 ponowiono na AI `64a4c71` w runie `37636569401`. Poprzednią
próbę zatrzymał hook awarii ignorujący nową linię na początku rzeczywistego SQL,
po full qualification/review/MLflow/registry i actual intake/cold worker.
[Receipt failed](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/blob/ai/10-ready/docs/evidence/ai10-v12-native-outbox-hook-failure.json)
nie poświadcza finalnego publishera ani Source API/UI. Nowy runner testuje
hook na SQL kompilowanym przez rzeczywisty emitter przed archiwum.

[Powtórzony stockout](stockout-final-head.json) i
[powtórzony anomaly](anomaly-final-head.json) na AI `433f5ed` przeszły pełne
oryginalne SQL publishery, read API i istniejący built UI. Zachowują oryginalne
kwalifikacje i piny Source, bez refitów.

- [x] Oryginalny Source capture do tego samego brokera i rzeczywistego AI SQL/ACK.
- [x] Native stockout/anomaly w prawdziwym Source API i istniejącym built UI.
- [x] Oryginalny publisher AI SQL stockout w pełnym nowym runtime.
- [x] Oryginalny publisher AI SQL anomaly w pełnym nowym runtime.
- [ ] Oryginalny v12 registry/SQL/publisher/Source API/UI na 102 dniach.
- [ ] Końcowy bounded raport i zielone Required CI obu dokładnych HEAD.
- [ ] Normalny protected merge obu PR-ów i zielone Required CI obu `origin/main`.

Pełna bieżąca instrukcja i receipts po stronie AI:
[AI10 acceptance](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/blob/ai/10-ready/docs/ai10-acceptance.md).
Oryginalnych historycznych receipts nie przepisujemy na wynik późniejszych prób.
