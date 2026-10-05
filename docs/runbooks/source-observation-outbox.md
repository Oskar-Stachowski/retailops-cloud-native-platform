# Source — operacyjny outbox obserwacji

Source zapisuje natywne wersje `daily_demand_versions` i ich zdarzenia
`source-observation-event-1.0` w jednej transakcji PostgreSQL. Kontrakt jest
przypięty do AI `b887b90e12036499870d0de455511f2cca4ba441`; schema byte SHA
znajduje się w `services/api/app/contracts/source-observations-v1/upstream.json`.
Nie zmienia to legacy v1, snapshotów, istniejących bundle ani modeli.

## Uruchomienie krok po kroku

1. Wdrożyć addytywną migrację `a10f0c7e0500` przez standardowy kontrolowany
   `alembic upgrade head`. Worker nie uruchamia migracji. Zachować backup
   wszystkich czterech nowych tabel i ich sequence razem z dotychczasową bazą.
2. Administrator brokera tworzy jawnie topic
   `retailops.source-observations.v1`: 1–32 partycje `0..N-1`, policy dokładnie
   `delete`, bez transakcyjnych producentów i compaction. Retention musi zachować
   historię potrzebną odbiorcy. Zmiana UUID topicu, klastra lub liczby partycji
   wymaga osobnego resync. Worker nie tworzy topiców ani ACL.
3. Utworzyć dedykowaną tożsamość SCRAM-SHA-256 albo SCRAM-SHA-512. Na tym topicu
   przyznać literal `WRITE`, `DESCRIBE`, `DESCRIBE_CONFIGS`; na klastrze
   `DESCRIBE` i `IDEMPOTENT_WRITE`. Nie przyznawać READ, CREATE, uprawnień do grup
   konsumentów ani innych topiców. Konfiguracja wymaga `SASL_SSL`, zaufanego CA
   i weryfikacji hostname. Dostęp SQL jest odrębny od principal brokera.
4. Ustalić stały `source_authority_id` UUID dla tej instancji źródła. Pierwszy
   zapis wiąże go z odkrytym cluster ID, native topic UUID i pełną liczbą partycji.
   Ten sam natywny topic nie może mieć drugiej authority w tej bazie. Identity
   nie jest ID zmieniającego się datasetu. Ustawić tę samą authority u odbiorcy AI.
5. Poza Git przygotować regularne pliki należące do operatora, dokładnie `0600`:
   `broker.json` i `database.json`, maksymalnie 16 KiB. Symlinki, duplikaty kluczy,
   nonfinite JSON i dodatkowe pola są odrzucane. Przykładowe kształty:

   ```json
   {"source_authority_id":"<stały UUID>","bootstrap_servers":"<host>:9092","username":"<SCRAM principal>","password":"<sekret>","ca_file":"<absolutna ścieżka do CA>"}
   ```

   ```json
   {"database_url":"postgresql://<dedykowany użytkownik>:<sekret>@<prywatny host>/<baza>"}
   ```

6. Dostarczyć wersję faktu jako prywatny JSON `0600`, maksymalnie 8 KiB, według
   przypiętego schema. Zachować natywne IDs, grain, UTC `available_at` i politykę
   `observed-quantity-history-1.0.0`. Nowa historia zaczyna od wersji 1, korekta
   ma nowy row ID i kolejną wersję; dostępność nie może się cofać. Statusy
   missing/null, closed/0 i observed_zero/0 pozostają odrębne.
7. Z rootu Source, w przypiętym środowisku API, zapisać fakt:

   ```sh
   PYTHONPATH=services/api services/api/.venv/bin/python services/api/scripts/source_observations.py append \
     --broker-config /private/broker.json --database-config /private/database.json \
     --fact /private/observation.json
   ```

   Zwracane `inserted` oznacza commit faktu i outboxu; `duplicate` oznacza
   identyczną już zapisaną wersję, bez drugiego zdarzenia. To nie potwierdzenie
   dostarczenia. Istniejący zapis domenowy może użyć `append_on_connection`
   w swojej transakcji; nie wolno commitować faktu osobno od outboxu.
8. Publikować ograniczoną partię:

   ```sh
   PYTHONPATH=services/api services/api/.venv/bin/python services/api/scripts/source_observations.py publish \
     --broker-config /private/broker.json --database-config /private/database.json \
     --max-messages 100 --max-seconds 60
   ```

   Ograniczenia: 1–20 000 wiadomości, 1–3600 sekund sprawdzanych między rekordami;
   pojedynczy flush maksymalnie 12 s. SIGTERM/SIGINT kończy między rekordami.
   Klucz i partycja są stałe dla observation ID. Worker wysyła oryginalne,
   kanoniczne bajty, dostępność jako timestamp oraz header wersji kontraktu.

## Awaria, wznowienie i rollback

Publisher serializuje authority blokadą jej wiersza SQL, także podczas
ograniczonego delivery. Odczytuje najstarsze pending zdarzenie, weryfikuje jego
bytes/hash/ID/partycję i związanie z zapisanym faktem. Dopiero dokładny udany
delivery callback oraz ponowna zgodność topologii pozwalają commitować SQL
`delivered_offset` i `delivered_at`. TLS/auth/ACL, metadata, baza lub callback
failure zatrzymuje instancję; nie przechodzi ona do następnego zdarzenia.

Nie ma rozproszonej transakcji broker–SQL. Crash po delivery i przed SQL commit
pozostawia pending; nowa instancja powtarza **te same bytes i event ID**.
Odbiorca AI zachowuje receipt każdego offsetu i deduplikuje ten sam fakt.
Idempotence producenta ogranicza retry w ramach jego instancji, a nie zastępuje
deduplikacji po restarcie. Nie należy ręcznie oznaczać pending jako delivered
ani kasować wcześniejszych wersji/outboxu w celu obejścia błędu.

Po błędzie zatrzymać publikację, przywrócić zweryfikowane połączenie/tożsamość,
sprawdzić backlog `delivered_offset IS NULL` i uruchomić nową instancję.
Kolizja faktu wymaga prawidłowej następnej wersji, bez przepisywania historii.
Uszkodzona baza wymaga spójnego backup/restore i reconciliation z brokerem;
nie odzyskiwać offsetów z samego high watermark.

Rollback aplikacji zachowuje nowe tabele. Downgrade schematu z choć jedną
authority jest blokowany; nie usuwa historii lub pending publikacji.

## Granica odbioru

Mandatory API CI uruchamia real PostgreSQL i pinned Redpanda TLS/SCRAM,
sprawdza atomic rollback, konkurencyjne writers, korekty/duplikaty, SQL disconnect
i SIGKILL po delivery przed commit, kolizje, integrity i identity, auth/policy.
Tylko własne tymczasowe kontenery i private files są usuwane. Raport i JUnit
są wymaganymi artefaktami. Dane wejściowe acceptance są jawne fixtures;
wykonywany producer/outbox jest kodem Source.

Ta ścieżka jest opt-in. Nie podłączono automatycznie legacy sales lub generatora
demo do historii obserwacji. Nie ustalono pełnego spójnego capture 43 tabel ani
snapshot/replay barrier. Potwierdzenia SQL publishera mogą nie zawierać offsetu
wcześniejszej wysyłki przerwanej przed commit, więc **nie są kompletnym wektorem
capture**. REST snapshot nadal unsupported, bundle `replay_handoff=false`.
Modele AI07/08, ich kwalifikacja i końcowe temporal E2E pozostają osobnym odbiorem.
