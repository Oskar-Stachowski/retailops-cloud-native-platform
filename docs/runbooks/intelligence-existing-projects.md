# AI 10 — overlay dla istniejących projektów Compose

`docker-compose.intelligence.yml` rozszerza istniejący projekt Source, a
[`infra/compose-intelligence.yaml`](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/blob/main/infra/compose-intelligence.yaml)
rozszerza osobny projekt AI. To wymagany artefakt połączenia usług; izolowany
[acceptance stack](intelligence-shared-runtime.md) zachowuje osobną rolę testową.
Pełne odebrane modele, SQL publishery, API/UI i zakresy auth wiąże
[raport AI10](../evidence/ai/10/README.md). Walidacja overlay nie jest nową kwalifikacją ML.

1. Przypnij oba commity. Ustal rzeczywiste nazwy należących do operatora projektów
   `SOURCE_PROJECT` i `AI_PROJECT` oraz absolutne katalogi checkoutów.
   Zapisz sekrety, konfigurację grantów Source i `ai.env`/`broker.json` AI poza Git.
   Wymagaj odczytów usługowych i osobistych principal zgodnie z
   [Source REST](source-reads-v2.md) i [modelami](intelligence-models-v2.md).
   Overlay nie zmienia istniejącej konfiguracji auth i nie dziedziczy demo admina.
2. Właściciel Source tworzy jedną dedykowaną sieć i zapisuje jej nazwę w
   `RETAILOPS_INTELLIGENCE_NETWORK` obu prywatnych plików środowiska:

   ```sh
   docker network create --label retailops.ai10.owner="$SOURCE_PROJECT" "$RETAILOPS_INTELLIGENCE_NETWORK"
   ```

   Nie używaj nazwy sieci obcej sesji. Oba overlay deklarują `external: true`;
   AI nie tworzy, nie przejmuje i nie usuwa tej sieci.
3. Najpierw sprawdź konfiguracje bez kontaktu z daemonem i bez drukowania sekretów:

   ```sh
   docker compose -p "$SOURCE_PROJECT" --env-file /private/source.env --profile dev \
     -f docker-compose.yml -f /private/source-auth.compose.yml \
     -f docker-compose.intelligence.yml config --quiet
   ```

   Prywatny `source-auth.compose.yml` to już skonfigurowane mounts/env grantów
   operatora, zgodne z podlinkowanymi runbookami; nie zapisuj go w repo.
   Po stronie AI prywatny plik env zawiera istniejące hasła lokalnego stosu oraz
   `RETAILOPS_INTELLIGENCE_NETWORK`, `AI10_PRIVATE`, `AI10_UID` i `AI10_GID`:

   ```sh
   docker compose -p "$AI_PROJECT" --env-file /private/ai-compose.env \
     -f compose.yaml -f infra/compose-intelligence.yaml config --quiet
   ```

4. Na własnym runtime operator Source dołącza wyłącznie istniejące `api`
   i `redpanda` przez te same pliki, wykonując `up -d api redpanda`.
   Pozostają na swoim dotychczasowym network; `db` nie dołącza do wspólnej sieci.
   API zyskuje alias `retailops-api`. Nie zmieniamy topic-init: legacy v1 oraz
   `retailops.intelligence.v2` nadal tworzy istniejący `redpanda-init`.
   Broker zachowuje wewnętrzny advertised listener `redpanda:9092`, rozwiązywany
   również na wspólnej sieci. Nie kieruj kontenera AI na `localhost:19092`.
5. AI dołącza własne `api` przez swój overlay. Alias `retailops-ai` jest odrębny
   od `retailops-api`; DB, migracje i MLflow pozostają poza wspólną siecią.
   Typowany REST klient używa `http://retailops-api:8000` i prywatnego grantu.
   Używaj istniejących procedur migracji i aktywacji modeli; overlay ich nie wykonuje.
6. Zbuduj oddzielny obraz delivery z istniejącego, zamkniętego locka brokera:

   ```sh
   docker compose -p "$AI_PROJECT" --env-file /private/ai-compose.env \
     -f compose.yaml -f infra/compose-intelligence.yaml --profile intelligence \
     build intelligence-delivery
   ```

   `AI10_PRIVATE` zawiera pliki `ai.env` i `broker.json`, zwykłe pliki `0600`
   należące do `AI10_UID:AI10_GID`; katalog jest montowany tylko do odczytu.
   `ai.env` wskazuje własne AI `db`, nigdy Source SQL. Broker configuration
   wskazuje Source `redpanda:9092` oraz właściwy dla tego brokera transport/grant.
   Bazowy Source Compose jest lokalnym demo; overlay nie nadaje mu TLS/SCRAM.
   Dla chronionego runtime zachowaj już skonfigurowane TLS/SCRAM i CA w prywatnej
   konfiguracji operatora; odbiór takiego transportu ma osobny actual receipt.
7. Po wcześniejszej atomowej publikacji uruchom bounded worker jawnie:

   ```sh
   docker compose -p "$AI_PROJECT" --env-file /private/ai-compose.env \
     -f compose.yaml -f infra/compose-intelligence.yaml --profile intelligence \
     run --rm --no-deps intelligence-delivery \
     python /ai/intelligence_outbox.py --env-file /private/ai.env \
     --broker-config /private/broker.json --max-events 100
   ```

   Dla native anomaly/stockout dodaj `--model-results`. Consumer Source używa
   własnego checkpoint/grantu i tego samego brokera według istniejącego runbooka.
   Zwykłe `up` nie włącza profilu delivery; worker nie uruchamia się w pętli.
   Sprawdzaj original SQL receipts i wynik w istniejącym API/UI.
8. Rollback: zatrzymaj tylko własny worker i cofnij dołączony overlay AI,
   zachowując outbox/history. `down` może dotyczyć wyłącznie potwierdzonego
   projektu AI; nie wykonuj go w checkout Source. Zewnętrzna sieć, Source broker,
   DB i volumes pozostają własnością Source. Sieć usuwa później jej właściciel,
   dopiero po odłączeniu wszystkich własnych usług; nie używaj globalnego prune.

W tej sesji nie uruchamiano lokalnego Docker ani istniejących stosów użytkownika.
Obie konfiguracje sprawdza rzeczywisty Compose CLI `config`, a Required CI AI
dodatkowo buduje zamknięty obraz delivery i sprawdza jego SDK/CLI bez sieci.
Rzeczywiste 40/1232/56 wyników i full SQL/broker/API/UI mają odrębne native receipts.
