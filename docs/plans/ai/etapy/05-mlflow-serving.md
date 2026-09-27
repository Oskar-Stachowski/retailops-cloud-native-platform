# 05 — Uruchom MLflow, batch i API

**Repo:** AI. **Zależność:** 04. **Wynik:** pierwszy działający przepływ snapshot → poprawny model → MLflow → persisted batch → read API. Streaming i projekcje RetailOps dochodzą w 10; minimalny lifecycle musi działać już tutaj.

## Wejście i granice

Potrzebne są manifesty, artefakty modelu i evidence 04 oraz baza/Compose ze szkieletu 01. [ML/API/lifecycle](../kontrakty/ml-api-lifecycle.md) jest wspólnym kontraktem dla forecastu, późniejszych anomalii i stockout. Nie kopiuj model binaries i wygenerowanych datasetów do Git. CLI z tego dokumentu jest docelowym interfejsem do zaimplementowania i opisania rzeczywistymi komendami.

## Małe PR-y

1. **Uruchom tracking i artifact store.** MLflow ma PostgreSQL backend w wydzielonej bazie/roli oraz trwały named volume na artefakty. Ogranicz sieć i uprawnienia; AI nie dostaje dostępu do bazy domenowej RetailOps. Zapisz wersje zależności, retencję, backup/restore metadata i artefaktów. Wymóg PostgreSQL jest decyzją architektoniczną tego projektu; nie myl metadanych registry z magazynem binaries.
2. **Podepnij istniejący run contract.** Loguj dataset/feature/split IDs, source i AI SHA, lock hash, seed/config, parametry, metryki i ich ważność, baseline delta, signatures, model/input example, raporty, środowisko, duration i checksumy. Loguj także rejected/failed runy. Artefakty 04 można zaimportować jako historyczne evidence z oryginalnym czasem i oznaczeniem importu; rejestracja nie wymaga udawania nowego treningu. Nie duplikuj evaluatorów.
3. **Wprowadź registry i kontrolowaną promocję.** Najpierw `retailops-demand-forecast`, następnie w 07/08 pozostałe modele. Używaj wersji immutable, aliasów `candidate`, `champion`, `rollback`, tagów i audytu. Wybór baseline’u jako championa jest prawidłowy. Polecenia review/reject/promote/rollback sprawdzają gates i role. Pierwszy release ma jawnie `previous_version=null`; przed demonstracją rollback utwórz i zachowaj dwie działające wersje. Nie uzależniaj implementacji od legacy MLflow stages.
4. **Zbuduj batch worker i trwałe runy.** POST tworzy run w DB, a oddzielny worker pobiera zadanie. Nie uruchamiaj treningu w handlerze HTTP ani nie opieraj trwałości kolejki wyłącznie na background task w pamięci. Wystarczy kontrolowana kolejka DB z leasingiem/heartbeatem i recovery po restarcie. Ustal retry, maksymalny czas, anulowanie wewnętrzne i obsługę wygasłego lease. Retry musi używać tej samej przypiętej wersji oraz datasetu.
5. **Przypnij model do release’u i runu.** Promocja rozwiązuje alias i tworzy release manifest z immutable model version + artifact checksum + image/config/schema. Worker ładuje tylko zatwierdzony artefakt z zaufanego registry i sprawdza checksum/signature. Restart nie może sam przełączyć modelu wskutek zmiany aliasu. Przyszły GitOps przeniesie ten sam manifest do desired state. Model utrzymuj stały przez życie procesu/runa; przełączenie wymaga nowego release’u lub jawnego kontrolowanego reload.
6. **Zapisuj wyniki atomowo.** Przetwarzaj w ograniczonych partycjach, waliduj count, unique grain, daty, domeny i freshness. Staging nie jest widoczne dla read API; dopiero zakończony run publikuje cały zestaw przez transakcję/pointer. Utrwal output manifest, content identity, pinned model i feature lineage. Niepowodzenie w połowie pozostawia poprzedni udany output i failed run. Ponowienie nie dubluje predykcji.
7. **Udostępnij forecast i lifecycle read API.** Implementuj health/ready/version/metrics, POST/GET forecast-runs, GET forecasts, models/versions/evaluation. Listy mają envelope, paginację, stabilne sortowanie, scope i jawne freshness. Output zawiera origin, target, target type, horyzont, model/version, source/feature/run IDs. `/ready` zależy od roli procesu: brak Bedrock nie blokuje czytania klasycznych prognoz. Odmowa auth, błędny scope, brak danych, stale data i awaria dependency mają odrębne odpowiedzi.
8. **Przygotuj granicę zdarzeń.** Utrwal kontrakt publikacji i identyfikatory wyników; na tym etapie batch/API nie zależy od działającego brokera. Pełny transactional outbox, publisher, retry i potwierdzone projekcje RetailOps implementuje 10. Nie deklaruj teraz dostarczenia eventu, jeśli powstała tylko prognoza. Po 10 prediction publication i outbox record należą do jednej transakcji, a status dostarczenia jest odrębny od sukcesu inference.
9. **Przećwicz rollback i recovery.** Pokaż odrzucenie kandydata bez zmiany runtime; następnie promocję, nieudany load/inference i powrót do znanej wersji wraz z config/schema. Zmiana aliasu, DB audit i konfiguracji nie jest jedną transakcją rozproszoną: użyj blokady/idempotentnego decision ID, zapisu kroków i weryfikacji postconditions. Przy przerwaniu promocji wznów z odczytanego rzeczywistego stanu; nie zgaduj, który model działa.

## Minimalne komendy operacyjne do udokumentowania

Docelowe operacje: `model-review`, `model-reject`, `model-promote`, `model-rollback`, `forecast-batch`, `inference-smoke`, `run-inspect`, `artifact-verify`, `backup`, `restore`. Nazwy możesz odwzorować na Make/CLI, ale README i runbook mają zawierać dokładnie te komendy, które zostały wykonane. Każda mutacja wymaga jawnych model/version, evidence ID i reason; nie przyjmuj arbitralnych ścieżek do pickle ani URL od klienta.

## Testy i zachowanie przy awarii

- Ten sam `Idempotency-Key` + to samo żądanie zwraca ten sam run; zmienione żądanie z tym kluczem daje 409. Persist key/request hash/run tworzą jedną transakcję.
- Restart workera po częściowym batchu prowadzi do bezpiecznego retry bez podwójnych wyników. Niekompletny output nie trafia do domyślnych list.
- Zmiana `champion` po rozpoczęciu joba nie zmienia jego model version. Restart istniejącego release’u nadal ładuje wersję przypiętą w manifestach.
- Brak modelu, uszkodzony checksum, niezgodny schemat lub failed gate blokują wykonanie/promocję. Brak dostępności MLflow nie powoduje pobrania przypadkowego lokalnego pliku.
- Read API może nadal pokazywać poprzedni kompletny output jako `stale`; nie oznacza go `current`. Run wymagający świeżych danych kończy się błędem.
- Viewer nie wywołuje batch/index/promotion, użytkownik nie odczytuje runa poza swoim scope. Client-supplied role/user ID nie jest tożsamością.
- Rollback odtwarza model/config/output compatibility; poprzednie predykcje są zachowane. Nie zastępuje odtworzenia uszkodzonej lub niekompatybilnej migracji DB.

## Artefakty i DoD

Compose i migracje, OpenAPI z przykładami, registry entries, model/evaluation cards, complete run logs, output manifest, audit before/after promotion, release manifest, backup/restore evidence oraz runbook rollback. Raportuj też cold load, batch duration, peak memory, artefact size i API latency.

**Gotowe, gdy:** świeży mały snapshot daje udany trwały batch i odczytywalną prognozę z pełną lineage; alias nie zmienia sam runtime; odrzucenie/promocja/rollback i restart workera zostały rzeczywiście przetestowane. To koniec pierwszego pionowego zakresu, a nie koniec całego portfolio. 07/08 korzystają z tej samej infrastruktury lifecycle.

## Prompt do Codex

```text
W repo retailops-ai-intelligence wykonaj etap05 po zaakceptowanym04.
Przeczytaj kontrakty/ml-api-lifecycle.md i zachowaj istniejący run/evaluator contract.
Uruchom MLflow+PostgreSQL+trwały artifact store, registry aliases i audyt decyzji.
Dodaj odporny na restart batch worker, atomową publikację persisted forecasts,
idempotentny POST202 i read API z autoryzacją/scope/freshness.
Przypinaj immutable model version oraz checksum w release i inference run.
Nie rozwiązuj mutable aliasu na każdy request/restart. Nie nazywaj niezrobionego
streamingu gotowym: outbox/broker/projekcje kończy10. Przetestuj crash/retry,
brak artefaktu, zmianę aliasu, reject/promote/rollback i backup/restore.
Zapisz OpenAPI, realne komendy, lineage i evidence pierwszego przepływu end-to-end.
```
