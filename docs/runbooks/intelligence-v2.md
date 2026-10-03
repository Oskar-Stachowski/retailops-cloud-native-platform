# AI 10 — forecast v2 i trwały odczyt

Status: pierwszy przyrost, **AI 10 in progress**. To osobna projekcja wyników
ML; `/forecasts`, heurystyczne `/inventory-risks` i demo user pozostają legacy.
Model fields pochodzą z wygenerowanego `V12ForecastItem` w repo AI.
Pin schema/registry jest w
`services/api/app/contracts/intelligence-v2/upstream.json`.
[Dowód przyrostu](intelligence-v2-evidence.md) podaje wykonane kontrole
i granice odbioru.

## Własność i zapis

AI odpowiada za weryfikację publikacji, tożsamość wyniku i atomowy outbox.
RetailOps waliduje transportowy topic oraz schema/relacje, zapisuje
`ai_forecast_results` i `ai_intelligence_inbox` w jednej transakcji, po czym
istniejący serial fail-stop runner wykonuje manual ACK. Awaria bazy/handlera
przerywa polling przed późniejszym offsetem. Crash po commit przed ACK
powtarza odczyt, z jednym efektem domenowym. Kolizja event/result identity
z odmienną treścią jest kwarantanną, nie nadpisaniem forecastu.

Kwarantanna, dokładne raw i pozycja transportu korzystają z istniejącego
[runbooka odtwarzania](realtime-recovery.md). Nieobsługiwane typy v2 są
odrzucane. Replay v2 w istniejącym CLI waliduje nowy schemat i używa key
grainu; v1 zachowuje dotychczasową walidację i key.

## Konfiguracja

1. Na własnej bazie RetailOps wykonaj `alembic upgrade head`. Nowy head to
   `a10f0c7e0200`; nie ma zmiany schematu tabel legacy.
2. Utwórz topic `retailops.intelligence.v2`, 3 partycje w lokalnym Compose.
   Zaktualizowany `redpanda-init` robi to poza pętlą legacy. Subskrypcje
   v1 pozostają zamknięte; dedykowana grupa to `retailops-intelligence-v2`.
3. Uruchom consumer z własnym `DATABASE_URL` i
   `RETAILOPS_BROKER_BOOTSTRAP_SERVERS`:

   ```sh
   PYTHONPATH=services/api python services/api/scripts/run_intelligence_consumer.py
   ```

   Lokalny runner korzysta z istniejącej konfiguracji prywatnego brokera.
   SASL/workload identity, overlay sieciowy i deploy są osobnym przyrostem.
4. Przygotuj **poza Git** plik policy, właściciel bieżący użytkownik, `0600`,
   zwykły plik, do 64 KiB. Ustaw ścieżkę w
   `RETAILOPS_INTELLIGENCE_ACCESS_POLICY`. Brak poświadczeń/policy nie
   dziedziczy demo admina. Nie umieszczaj service token w Vite env ani JS.

   Format policy:

   ```json
   {
     "version": "retailops-intelligence-access-1.0",
     "principals": [{
       "principal_id": "approved-reader",
       "credential_sha256": "SHA256_OF_PRIVATE_RANDOM_TOKEN",
       "capabilities": ["forecast:read"],
       "product_ids": ["APPROVED_PRODUCT_ID"],
       "selling_location_ids": ["APPROVED_LOCATION_ID"],
       "channels": ["store"],
       "release_ids": ["APPROVED_V12_MODEL_RELEASE_ID"]
     }]
   }
   ```

   Placeholdery trzeba zastąpić prawidłowymi, zatwierdzonymi ID/hash.
   Token ma 32–256 znaków; wygeneruj losowy i zachowaj poza repo.
   Policy ogranicza do 20 produktów, 5 lokalizacji, 2 kanałów i 32 release.
   Nie ma wildcard ani możliwości nadania admin actions. Duplikaty principal
   lub credential hash są błędem konfiguracji. Zmiana policy/revocation
   wymaga restartu API (cache przypina jedną wersję na proces).
5. Wywołaj API przez `Authorization: Bearer <private token>`.

## Read API

- `GET /intelligence/v2/forecasts` ma domyślny limit 50, maksymalny 100,
  offset do 2800 i bounded candidate view do 2800 wyników.
- Filtry: `product_id`, `selling_location_id`, `channel`, `inference_run_id`,
  `release_id`. Niewskazany filtr oznacza wyłącznie grant principal.
  Jawny niedozwolony scope daje 403; unknown query, w tym demo `user_id`
  i niepoprawny `store_id`, daje 422.
- `GET /intelligence/v2/forecasts/{prediction_id}` zwraca konkretny wynik;
  obcy lub nieistniejący ID daje 404. Odczyt nie uruchamia modeli ani Bedrock.
- `forecast` jest pełnym oryginalnym payloadem, `source=retailops-ai`,
  `received_at` opisuje projektor. Oddzielne `freshness` ocenia origin age
  i expiry approval na czas odczytu; nie odmładza starego wyniku arrival time.
- Semantyka `selection=immutable_history`. Kolejność to origin, publication
  generated_at i ID, malejąco; starszy replay nie zastępuje nowszego wyniku.
  Nie ma jeszcze approved-head „latest” ani agregacji do legacy `/forecasts`.
- Kolejna strona wymaga `view_sha256` z pierwszej. View wiąże principal,
  grant, filtry i IDs. Zmieniony zbiór daje 409, zamiast utraty rekordów przy
  zwykłym offset pagination. To bounded history read, **nie snapshot eksportowy**.
- Niedostępna baza daje bezpieczne 503; nie zastępuje danych przez zero/demo.
  OpenAPI zawiera kopię rzeczywistego schematu ML w komponentach `AI10_*`.

## Testy, naprawa i kolejny przyrost

```sh
make integration-replay-test
make integration-failure-test
```

Oba cele korzystają z `API_VENV_PYTHON`; wymagają przygotowanego środowiska
API i Docker. Fixture uruchamia wyłącznie własne PostgreSQL/Redpanda na
losowych portach, a cleanup usuwa tylko te dwa kontenery/ich wolumeny.
JUnit trafia do `ci-cd/reports/ai10/`. Pre-pull obu przypiętych obrazów usuwa
czas pobierania z bounded timeout testu. Fixture forecast jest jawnie
`-mechanics`: test potwierdza trwałość/kontrakt, nie jakość modelu.

Drill obejmuje duplicate, original lineage w rzeczywistym read API,
late older result, rollback częściowej projekcji, invalid JSON/UTF-8/raw,
kolizję tożsamości, SIGKILL po DB commit przed ACK, niedostępność DB/
kwarantanny, brak luki offsetów, 0/1/102 rekordy i zmianę view między stronami.
Nie testuje jeszcze rebalance wielu równoległych procesorów ani snapshot
korekt sprzedaży. Ten consumer jest synchroniczny i przerywa polling przy
każdym niepotwierdzonym błędzie; nie zwiększaj jego współbieżności przed
wdrożeniem dodatkowego checkpoint/fencing.

Rollback: zatrzymaj własny consumer v2, wyłącz publikację eventów po stronie
AI, zachowaj tabele, raw i pending outbox. Nie usuwaj wspólnego runtime lub
wolumenów. Ponowne uruchomienie tej samej grupy kontynuuje od ostatniego
trwale potwierdzonego offsetu. Błąd identity wymaga weryfikacji oryginalnego
wyniku i jawnego replay przez operatora, bez ręcznego nadpisania projekcji.
Zgodność starszej aplikacji z nowymi tabelami ma osobny checksum-pinned plan
i próby w [runbooku rollbacku](application-rollback.md). Plan nie pozwala na
arbitralną zmianę historii migracji ani destructive downgrade.

Otwarte do całego AI 10: wyniki 07/08 i ich publiczne schematy, sugestia fixture,
approved latest policy, upstream REST/export/snapshot+replay, shared Compose
overlay i transport auth, rozszerzona telemetry, istniejący frontend oraz
E2E rzeczywistych trzech modeli na profilu 102 dni. Testy tego przyrostu
nie zamykają Definition of Done całego etapu.
