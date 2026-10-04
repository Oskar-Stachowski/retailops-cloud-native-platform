# AI10 — trwała projekcja sugestii wymagających przeglądu człowieka

## Zakres i kwalifikacja

Ten przyrost dostarcza odbiór fixture `recommendation_generated` na istniejącym
`retailops.intelligence.v2`, osobną projekcję PostgreSQL, atomowy checkpoint oraz
osobisty odczyt HTTP. Schemat `PersistedSuggestion` i schemat kandydata są kopiami
**identycznych bajtów** z AI12 `a14b7899d9366c6ae555c0b6be4a8d027514ca91`.
`owner.json` przypina również kod walidatorów, kanonikalizacji i tworzenia UUID.
Commit AI12 jest lokalny i jeszcze nieopublikowany. Schematy porównano lokalnie
z niezmiennymi plikami przez `git show`; checker opcjonalnie używa `--owner-root`
do ponownego porównania kodu właściciela na tym komputerze. CI sprawdza checksumy
zapisanych schematów, zgodność envelope z payloadem i mechanikę adaptera.
**CI nie sprawdza uruchomienia oryginalnego kodu AI12 ani zdalnej dostępności
tego commita.** Prywatny kod AI12 nie jest kopiowany do repozytorium RetailOps;
nie publikujemy ani nie modyfikujemy jego sesji/brancha.

**Status adaptera: `fixture_only`.** AI12 w tym commicie zapisuje sugestie we
własnej bazie asystenta; nie ma uzgodnionego emitera outbox dla tego eventu.
Dotychczasowy rejestr producenta v2 i jego prognozy zachowują swoje bajty.
Osobny rejestr adaptera jest w `intelligence-suggestions-v1/registry.json`.
Przełącznik fixture jest domyślnie wyłączony. Ten odbiór nie kwalifikuje agenta,
modeli ani danych operacyjnych; nie zamyka capture/replay, UI sugestii ani
three-model E2E na 102 dniach.

## Uruchomienie w odizolowanym środowisku odbioru

1. Użyj własnego checkoutu, osobnej bazy PostgreSQL i własnej grupy checkpointed
   consumer. Nie wykonuj migracji, seedowania ani resetu offsetów na współdzielonej
   bazie lub grupie. Lokalne sesje AI07/08 pozostają poza tym przepływem.
2. W tej własnej bazie wykonaj `alembic upgrade head`. Nowy head to
   `a10f0c7e0400`; historyczne migracje nie zmieniają bajtów.
3. Włącz `RETAILOPS_ENABLE_SUGGESTION_FIXTURE_TRANSPORT=1` **wyłącznie w workerze
   środowiska odbioru fixture**. Bez tego poprawna sugestia jest odrzucana i
   kwarantannowana jak nieobsługiwany typ; domyślny worker prognoz działa dalej.
   Nie wysyłaj fixture na współdzielony broker używany przez inne grupy.
4. Worker używa istniejącego modułu
   `python -m scripts.run_checkpointed_intelligence_consumer` i konfiguracji
   opisanej w runbooku checkpointów. Zachowaj TLS/SCRAM, jawne bootstrap i własną
   grupę. Przykładowy fixture ma historyczny termin ważności: jest przeznaczony
   do sprawdzenia historii i deduplikacji, a nie aktywnej decyzji.
5. Przygotuj osobistą politykę odczytu w prywatnym pliku regularnym `0600`,
   należącym do użytkownika procesu API, bez symlinków ani hardlinków. Wskaż ją
   przez `RETAILOPS_INTELLIGENCE_SUGGESTION_ACCESS_POLICY`. Dopuszczalny rozmiar
   to 64 KiB i 32 principal. API czyta plik na nowo przy każdym żądaniu.

   Przykład struktury; zastąp przykładowe identyfikatory i digest własnymi:

   ```json
   {
     "version": "retailops-suggestion-access-1.0",
     "principals": [{
       "principal_id": "operator-1",
       "credential_sha256": "<sha256 osobistego poświadczenia>",
       "capabilities": ["suggestion:read"],
       "product_ids": ["<product>"],
       "selling_location_ids": ["<store UUID>"],
       "channels": ["store"],
       "policy_sha256s": ["<sha256 polityki decyzji AI12>"],
       "agent_config_versions": ["<wersja konfiguracji agenta>"],
       "model_release_refs": ["<dokładny dozwolony model release ref>"]
     }]
   }
   ```

   Granty polityki/configu określają widoczność, a nie zatwierdzenie jakości.
   **Każdy** ref modelu w sugestii musi być dozwolony. Pusta lista w payloadzie
   jest poprawna dla `refresh_source_data`, który nie wyprowadza decyzji z modelu.
   Poświadczenie prognoz i `user_id=platform-admin` nie nadają tego grantu.
6. Dla wydzielonych ról SQL nadaj API tylko `SELECT` na
   `ai_recommendation_results`; worker potrzebuje `SELECT, INSERT` na tej tabeli
   i `ai_recommendation_inbox` oraz istniejących uprawnień checkpointu/kwarantanny
   (`SELECT, INSERT, UPDATE` odpowiednich tabel). Worker nie potrzebuje
   `UPDATE`/`DELETE` na wynikach sugestii. Nie używaj roli migracyjnej do odczytu.
7. Wywołuj API przez zaufany HTTPS/proxy z osobistym Bearer w pamięci. Nie
   przekazuj go w query, URL, historii shell, logach ani browser storage.
   Ten przyrost nie uruchamia lokalnego Dockera ani nie zmienia wdrożenia.

## Semantyka odczytu

- `GET /intelligence/v2/recommendations` domyślnie wybiera `current`: publikacja
  już nastąpiła i `now() < expires_at` według zegara PostgreSQL. Żaden caller
  nie wybiera własnego zegara ani nie przedłuża pięciominutowego życia.
- `selection=immutable_history` zachowuje oryginalny payload, także wygasły i
  po spóźnionym replay. Wrapper `freshness` jest obliczany przy odczycie:
  `suggestion_expired` lub `publication_in_future`. Zapisane
  `freshness_status=current` opisuje publikację, nie bieżący odczyt.
- `GET /intelligence/v2/recommendations/{UUID}` zwraca dokładny oryginalny
  payload i pełne evidence/model refs/trace/answer/candidate/policy/config.
  Niedozwolony lub nieistniejący wynik daje identyczne `404`.
- Filtry: product, selling location, channel i trace. Nieznane/powtórzone query
  są odrzucane (`422`), jawny filtr poza grantem daje `403`; brak osobistego
  poświadczenia daje `401`, uszkodzona polityka lub projekcja `503`.
- Strona ma maksymalnie 50 rekordów; widok maksymalnie 500 i 8 MiB. Kolejna
  strona wymaga `view_sha256`. Digest wiąże principal, granty, filtry, wybór i
  identyfikatory/hash payloadów. Nowy wynik, zmiana grantów lub wygaśnięcie
  zmienia widok i daje `409`. Odczyt ma repeatable-read i limit SQL 3 s.
- Cały zasób, również błędy, ma `Cache-Control: no-store` i `Vary: Authorization`.
- `requires_human_review=true`, `status=proposed` i
  `execution_authorized=false` są zachowane. Brak endpointu accept/execute,
  automatycznego zamówienia, ilości, progu confidence i przełączenia na workflow
  istniejącej tabeli `recommendations`.

## Trwałość, replay i awarie

Event UUID5 wiąże typ i recommendation UUID; recommendation UUID5 i answer
UUID5 wiążą trace oraz hash kandydata. Candidate hash normalizuje UTC zgodnie
z kodem AI12. Źródło poprzedza publikację; życie to `(0, 300]` sekund.
Obowiązkowy boolean musi być literalnym `true`; liczba `1` jest odrzucana.
Evidence refs nie są puste ani powtórzone, podobnie model refs.

W jednej transakcji Source zapisuje wynik, deduplikujący inbox, transport
receipt i kursor. Receipt wskazuje dokładnie jeden z forecast/suggestion
albo kwarantannę. Zapisany UUID z innym body jest kolizją: oryginał pozostaje,
surowy event trafia do kwarantanny, a worker może przetworzyć następny rekord.
Błąd bazy po stagingu cofa wszystkie efekty i nie wykonuje ACK. SIGKILL po
commit, przed ACK, powoduje replay istniejącego receipt bez drugiego efektu.

Operator może użyć istniejącego jawnego narzędzia replay kwarantanny tylko
po przeglądzie przyczyny. Zachowuje ono payload/UUID i grain partycji.
Spóźniony event nie przywraca wygasłej sugestii do `current`.

## Odbiór i rollback

Lokalnie uruchamiane są kontrakty/auth/regresja oraz static gates. Realne
PostgreSQL/Redpanda, SIGKILL, checkpoint, API i ograniczenia SQL są
**obowiązkowe w Required CI** (`REQUIRE_BROKER_TESTS=1`). Nowe testy trwałości
są wykonywane przed broad regression; broad ich nie powtarza. Artefakt
`intelligence-suggestion-evidence` zawiera raport pinów i JUnit rzeczywistych
testów trwałości. Bramka UI prognoz dalej używa własnego PG/Chromium.

Starszy test restartu brokera może dostać przejściowe `NOT_COORDINATOR` podczas
samego odczytu zachowanych offsetów. Pomocnik obserwacji ma limit 10 sekund
i ponawia wyłącznie cztery błędy gotowości koordynatora. Nie wykonuje commit ani
resetu, błędy autoryzacji przerywają go natychmiast. Worker, ACK i fencing nie
zmieniają zachowania. Osobne testy potwierdzają deadline i brak ukrywania auth.

Compose i Kubernetes migrują raz do nowego head, zapisują niepuste wyniki
forecast/suggestion, oba inboxy i dwa transport receipts. Następnie sprawdzają
ten sam snapshot wszystkich tabel przez upgrade, restart i rollback obrazu.
Nie ma downgrade, reseed ani restore zastępującego rollback aplikacji.
Fingerprint migracji i plan kompatybilności wskazują konkretny head/historię.
Jawny downgrade schematu do `a10f0c7e0300` jest odrzucany, gdy istnieją sugestie
lub ich receipts; potwierdza to test na prawdziwym PostgreSQL.

Przed przyszłą publikacją rzeczywistego emitera trzeba uzgodnić z AI12
atomowy outbox, upstream registry/schema, uprawnienia transportu i odbiór
konkretnej publikacji asystenta. Następnie powiązać wygasanie i zmiany aktywnego
modelu z decyzją agenta, dodać UI przeglądu i przeprowadzić końcowy AI10 E2E.
