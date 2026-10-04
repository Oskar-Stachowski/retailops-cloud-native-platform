# AI 10 — wybór aktywnej publikacji prognozy

Ten przyrost udostępnia `GET /intelligence/v2/forecasts/active` przez istniejące
prywatne credentials `forecast:read`. Wybór jest **jawną decyzją operatora**,
przypiętą do jednej kompletnej publikacji, release'u, runu i origin. Historia
`GET /intelligence/v2/forecasts` nadal przechowuje niezmienne wyniki.

Grant odczytu nie jest zgodą ML. `quality_status=passed_at_publication` opisuje
przeszłą publikację, a `received_at` nie odnawia dopuszczenia ani świeżości.
Endpoint nie kontaktuje się z MLflow i nie nadaje modelowi statusu `approved`.
Odpowiedź jawnie podaje `approval_authority=private_operator_selection`.

## Granica zaufania i zgodność właściciela

Operator przekazuje prywatny raport istniejącego polecenia AI
`scripts/mlflow_v12_lifecycle.py review`, przypiętego do commitu
`3a64b03ac707a7bc041bef4ad80e451c9ff8e49a` i SHA-256
`167dc435ac1be4a2ae2b676724aedab42f88b9e4f2df86dfdfa866e858d74cfb`.
Pin jest w `services/api/app/contracts/intelligence-head-v1/owner.json`;
Required CI porównuje plik z rzeczywistym istniejącym checkoutem AI.

Polecenie właściciela uwierzytelnia **model operatora**, blokuje model w
lifecycle i sprawdza pełny binding/kapsułę w MLflow. RetailOps wymaga w jego
raporcie zgodnego namespace/wersji/approval SHA/release'u, champion wybranej
wersji, `rejected=false` i pustych `pending_decisions`. Polityka wiąże
canonical SHA-256 całego raportu oraz oddzielny operator review time.
Raport zachowuje `runtime_status=not_integrated`; RetailOps nie zmienia tego pola.

Prywatny plik operatora jest granicą zaufania, podobnie jak konfiguracja
grantów. Checksum nie jest podpisem cyfrowym. API nie potwierdza autentyczności
raportu przez zdalne wywołanie ani nie wykrywa samodzielnie późniejszej decyzji
MLflow. Operator musi odebrać raport z autoryzowanego runtime AI, bez ręcznych
zmian pól, i wycofać wybór przy odrzuceniu/zmianie lifecycle. Mechanizm
automatycznej dystrybucji unieważnień pozostaje dalszą pracą.

Decyzja ma termin liczony od rozpoczęcia przeglądu: domyślnie 5 minut,
maksymalnie 15 minut, zawsze przed `approval_valid_until`. Czas w przyszłości
blokuje widok. Samo ponowne przygotowanie pliku ze starym review time nie
przedłuża zgody. Po wygaśnięciu API zwraca 503; do odnowienia potrzebny jest
**nowy przegląd właściciela**, nie ponowna publikacja starego artefaktu.

## Przygotowanie krok po kroku

Wykonuj poniższe operacje dopiero na własnym, autoryzowanym runtime z
rzeczywiście dopuszczonym modelem. Ten PR nie uruchamia ich na sesjach AI 07/08
ani na współdzielonym stosie. Pliki prywatne pozostają poza Git.

1. Przypnij commit AI powyżej i przyrost RetailOps. Wybierz opublikowany,
   zakończony run z namespace `retailops-demand-forecast-v12`, zgodny z bieżącym
   head i champion właściciela. Mechanics i development są odrzucane. Przy
   rollbacku wybierz publikację z aktualnym release ID; retry starego `publish`
   nie zmienia tego ID i nie odnawia dopuszczenia.
2. W środowisku AI zapisz osobno prywatne JSON: pełną publikację, `get` runu
   i `receipt`, używając istniejącego uwierzytelnionego CLI
   `scripts/forecast_v12_queue.py`. Ustaw `umask 077`. Użyj własnego pipeline
   policy/credentials i konkretnego run ID. Zwykły wynik obliczeń bez publikacji
   nie jest dopuszczalnym wejściem.
3. Z tych trzech plików przygotuj **cały** event export, używając istniejącego
   `forecast_events`. Nie sklejaj kilku runów ani stron z innym view hash.
   Przykład do wykonania w venv AI (ścieżki zastąp własnymi):

   ```python
   import os
   from pathlib import Path
   from retailops_ai.data_contracts.identity import canonical_bytes
   from retailops_ai.forecast_jobs.v12_batch import V12BatchRun, V12BatchReceipt
   from retailops_ai.forecast_jobs.v12_publication import V12Publication
   from retailops_ai.intelligence_events.contracts import forecast_events

   output = V12Publication.model_validate_json(Path('/private/ai10/output.json').read_bytes())
   run = V12BatchRun.model_validate_json(Path('/private/ai10/run.json').read_bytes())
   receipt = V12BatchReceipt.model_validate_json(Path('/private/ai10/receipt.json').read_bytes())
   events = forecast_events(output, run, receipt)
   raw = canonical_bytes([event.model_dump(mode='json') for event in events])
   fd = os.open('/private/ai10/events.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
   with os.fdopen(fd, 'wb') as stream:
       stream.write(raw)
   ```

   Funkcja weryfikuje kompletną publikację, run, receipt i oryginalne wartości
   ML. Dalszy wybór wymaga całego scope publikacji, do 20 produktów,
   5 lokalizacji, jednego kanału i wszystkich 7 albo 14 horyzontów.
4. Zapisz UTC **przed** wywołaniem przeglądu, następnie wykonaj istniejące
   polecenie jako uprawniony model operator, z wersją publikacji na stdin.
   Zachowaj cały prywatny stdout JSON i kod zakończenia; błąd kończy procedurę:

   ```sh
   umask 077
   AI10_REVIEWED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
   .venv/bin/python scripts/mlflow_v12_lifecycle.py \
     --env-file /private/ai10/ai.env \
     --policy-file /private/ai10/operator-policy.json \
     --credentials-file /private/ai10/operator-credentials.json \
     review --model retailops-demand-forecast-v12 \
     < /private/ai10/version.json > /private/ai10/owner-review.json
   ```

   `version.json` ma wyłącznie `{"model_version":"WERSJA"}`. Nie przekazuj
   policy czy credentials czytelnikowi API. Sprawdź brak odrzucenia/pending,
   zgodność aktywnego release/champion z wybraną publikacją i ważność jej
   dopuszczenia. Raport `review` nie jest nową decyzją promocji.
5. Bez ponownego ustawiania `AI10_REVIEWED_AT` przygotuj plik w venv RetailOps.
   Podaj każdy produkt/lokalizację pełnej publikacji przez powtarzane argumenty:

   ```sh
   PYTHONPATH=services/api python services/api/scripts/prepare_intelligence_head.py \
     --events-file /private/ai10/events.json \
     --owner-review-receipt-file /private/ai10/owner-review.json \
     --reviewed-at "$AI10_REVIEWED_AT" \
     --reviewed-by OPERATOR_ID --review-seconds 300 \
     --product PRODUCT_ID --selling-location LOCATION_ID --horizon 7 \
     --output /private/ai10/head.next.json
   ```

   CLI sprawdza schematy, piny, pełny grain i hashe. Odrzuca brakujące wiersze,
   powtórzone grain/IDs, inne namespace, mieszane modele/release/run/origin,
   stary lub przyszły review time oraz niespójny raport operatora.
   Zapis jest atomowy, 0600, wyłącznie do nowego pliku. Istniejący plik nigdy
   nie jest nadpisywany. Exit 2 ma stały bezpieczny komunikat bez danych prywatnych.
6. Dopiero po przeglądzie przygotowanej polityki operator aktywuje ją przez
   atomowy rename do własnej skonfigurowanej ścieżki. Ustaw
   `RETAILOPS_INTELLIGENCE_HEAD_POLICY=/private/ai10/head.json` w API oraz
   osobne istniejące `RETAILOPS_INTELLIGENCE_ACCESS_POLICY` czytelników.
   Sam CLI zwraca `activated=false` i nie konfiguruje ani nie restartuje API.
   Dla kontenera montuj prywatny **katalog** read-only, aby atomowy rename
   był widoczny; bind pojedynczego starego inode pliku nie wystarcza.
7. Sprawdź uwierzytelniony endpoint `/intelligence/v2/forecasts/active`.
   Opcjonalnie przypnij `release_id`, `inference_run_id` i UTC `as_of`.
   API weryfikuje całą publikację także poza stroną/grantem czytelnika, a
   zwraca wyłącznie dozwolone product/location/channel/release.
   Niekompletna dostawa zwraca 503, bez częściowego aktywnego wyniku.
8. Odnawiaj przez nowy przegląd i nowy plik. Przy odrzuceniu modelu albo
   zmianie owner head wycofaj politykę we wszystkich replikach. Brak/usunięcie
   pliku daje 503. Polityka z pustymi `heads` daje `200/no_data` i musi mieć
   poprawny canonical `policy_sha256`. Polityka jest odczytywana na początku
   każdego żądania; request rozpoczęty wcześniej zachowuje swój spójny snapshot.

## Widok, awarie i limity

- Spóźniona starsza lub nowsza wiadomość nie zmienia wyboru. Tylko nowa
  prywatna polityka aktywuje inny release/run/origin. Historię zachowano.
- Wszystkie oczekiwane prediction IDs i canonical SHA payloadu muszą być
  dostarczone, bez dodatkowych wierszy tego samego output ID. Pełny coverage
  produktu/lokalizacji/horyzontu jest sprawdzany przed filtrowaniem i paginacją.
- DB używa `REPEATABLE READ READ ONLY`, timeoutu SQL 3 s i preflight byte
  budget przed pobraniem payloadów. Maksymalnie 32 niezależne publikacje,
  2800 oczekiwanych wierszy łącznie i 16 MiB payloadów; 100 na stronę.
  Nakładające się serie albo powtórzony output ID w polityce są odrzucane.
- Plik polityki ma limit 1 MiB, raport 64 KiB, export 16 MiB. Wymagany jest
  zwykły plik właściciela procesu, bez praw grupy/innych, symlinków i FIFO.
  Powtórzone klucze JSON i dodatkowe pola nie przechodzą.
- `view_sha256` wiąże principal, granty, filtry, cały wybór i prediction IDs.
  Offset wymaga hasha; zmiana polityki daje 409. Zmiana samego zegara/freshness
  nie zmienia view. Nieznane/powtórzone parametry lub czas bez UTC dają 422.
- `freshness` nadal odzwierciedla źródła i wiek origin; aktywny wybór nie
  zamienia `unknown`/`stale` na `current`. API nie zna nowych nieopublikowanych
  runów po stronie AI ani liveness workera na podstawie samego wyboru.
- Brak nowych tabel/migracji i brak write API. Przy rollbacku aplikacji
  wyłącz wybór, zachowaj historię/checkpointy i istniejący plan addytywny.

## Odbiór

```sh
PYTHONPATH=services/api python -m pytest -q services/api/tests/test_intelligence_head.py
PYTHONPATH=services/api REQUIRE_BROKER_TESTS=1 python -m pytest -q \
  services/api/tests/test_intelligence_head_durability.py
```

Drugi zestaw używa własnych jednorazowych PostgreSQL/Redpanda i rzeczywistego
ASGI API, w tym pełnej dostawy przez checkpointowany consumer. Payloady oraz
raport operatora są jawnie wymyślonym **mechanics fixture o kształcie production**;
nie są dowodem kwalifikacji, promocji ani zatwierdzenia rzeczywistego modelu.
CI wykonuje drille przed szeroką regresją, scala coverage i wymaga 80%.
Pozostają: zdalna dystrybucja unieważnień, wspólny broker/oddzielne DB/auth,
pełny input snapshot/replay, rzeczywiste AI 07/08, UI i 102-dniowe cross-repo E2E.
Cały AI 10 pozostaje `in_progress`.
