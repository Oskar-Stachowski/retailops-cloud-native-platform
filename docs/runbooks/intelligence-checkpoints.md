# AI 10 — trwałe checkpointy i fencing partycji

Status: przyrost AI 10, cały etap **in progress**. Ten prywatny, synchroniczny
consumer zapisuje w jednej transakcji prognozę lub dokładną kwarantannę,
potwierdzenie transportu i następny offset. Dopiero po commit bazy wykonuje
synchroniczny Kafka ACK i sprawdza jego konkretną pozycję.

## Zakres gwarancji

- `ai_intelligence_partitions` przypina cluster ID, topic UUID, początek pokrycia,
  następny offset, owner UUID i monotonny epoch dla każdej grupy/partycji.
- Każdy zapis blokuje wiersz partycji. Claim nowego workera czeka na rozpoczętą
  transakcję, zwiększa epoch, a starego ownera blokuje przed kolejnym efektem.
  Spóźniony release starej dzierżawy nie usuwa nowego ownera.
- `ai_intelligence_transport` wiąże pozycję z SHA-256 wartości, key, timestampu
  i uporządkowanych nagłówków, zachowując powtarzające się nazwy i null.
  Powtórzony odczyt identycznej pozycji nie zapisuje drugiego efektu. Zmieniona
  treść pod tą samą pozycją zatrzymuje konsumenta.
- Kolizja tożsamości biznesowej trafia do kwarantanny. Savepoint wycofuje
  częściową projekcję, a kwarantanna i cursor zatwierdzają się razem.
  Błąd bazy lub zapisu checkpointu wycofuje całość i zatrzymuje polling bez ACK.
- Crash po DB commit przed Kafka ACK prowadzi do ponownego odczytu od starszego
  offsetu brokera i weryfikacji trwałego potwierdzenia. Brak Kafka commit przy
  istniejącym stanie DB pozwala wznowić od udowodnionego cursora DB.
- Zmiana cluster/topic UUID, utrata potrzebnego logu, cofnięcie log high albo
  broker commit wyprzedzający DB cursor zatrzymują claim. Nie resetuj tego stanu
  ręcznie; najpierw ustal przyczynę i przygotuj zweryfikowane odtworzenie.

Obsługiwany log jest **delete-only, bez transakcyjnych producentów, z ciągłymi
pozycjami dostarczanych rekordów**, do 32 partycji. Obecny publisher v2 jest
idempotentny i nietransakcyjny. Kafka może mieć luki po control records,
aborted transactions lub compaction. Ten przyrost odrzuca compaction podczas
inspekcji konfiguracji i zatrzymuje się przy każdej luce; nie dowodzi ciągłości
przez samo `high watermark`. Nie używaj tego runnera dla transactional topic.
Rozszerzenie o dowód pominiętych pozycji jest osobną zmianą.

Bootstrap wyznacza **nową granicę pokrycia**: istniejący commit tej nowej grupy,
co najmniej log low, albo log low przy braku commit. Nie odtwarza usuniętych
rekordów, nie ustanawia snapshot boundary i nie zapewnia pełnej historii sprzed
bootstrapu. Snapshot+replay handoff jest nadal `unsupported`. Osobne grupy
mogą wspólnie deduplikować wyniki biznesowe, ale mają odrębne checkpointy.

## Uruchomienie krok po kroku

1. W izolowanej, własnej bazie wykonaj `alembic upgrade head` z katalogu
   `services/api`. Head `a10f0c7e0300` dodaje dwie tabele do wcześniejszej
   projekcji/inbox; istniejące migracje pozostają niezmienione.
2. Sprawdź właściciela brokera, topic `retailops.intelligence.v2`, politykę
   `cleanup.policy=delete`, producentów bez transakcji i zakres uprawnień.
   Konto potrzebuje odczytu topicu, odczytu/zapisu commit swojej grupy oraz
   Describe topic/cluster i DescribeConfigs topicu. Weryfikacja topic UUID jest
   obowiązkowa. Runner korzysta z eager `range` i `read_committed`.
3. Przygotuj poza Git zwykły plik JSON należący do użytkownika procesu,
   dokładnie `0600`, do 64 KiB. Symlink i FIFO są odrzucane. Przykład:

   ```json
   {
     "bootstrap_servers": "PRIVATE_BROKER_HOST:9093",
     "security_protocol": "SASL_SSL",
     "sasl_mechanism": "SCRAM-SHA-256",
     "username": "PRIVATE_WORKLOAD_USER",
     "password": "PRIVATE_WORKLOAD_PASSWORD",
     "ca_file": "/private/path/ca.pem"
   }
   ```

   Podstaw rzeczywiste poświadczenia poza repo. Dopuszczone są SASL_SSL
   (SCRAM-SHA-256/512 lub PLAIN) oraz SSL z weryfikacją TLS librdkafka.
   PLAINTEXT wymaga jawnego `allow_plaintext_loopback=true` i wyłącznie
   endpointów localhost/127.0.0.1/::1; służy izolowanym testom.
   Plik nie przyjmuje ustawień ACK ani innych dowolnych opcji librdkafka.
4. Ustaw `DATABASE_URL` na własną bazę. Użyj osobnej grupy, domyślnie
   `retailops-intelligence-v2-checkpointed`. Nazwa wcześniejszej grupy
   `retailops-intelligence-v2` jest odrzucana, aby nie przejąć jej offsetów.
5. Odczytaj status bez inicjalizacji, claim, projekcji i Kafka ACK:

   ```sh
   PYTHONPATH=services/api python services/api/scripts/run_checkpointed_intelligence_consumer.py \
     --broker-config /private/path/broker.json --status
   ```

   Status podaje per-partycja low/high, broker commit, granicę pokrycia,
   DB cursor/epoch, wiek checkpointu i backlog liczony w offsetach. Wykazuje
   zmianę stream identity, retention gap, cofnięcie high oraz commit przed DB.
   `owner_claimed` nie oznacza żywego workera, a backlog nie ocenia świeżości
   biznesowej prognoz. Nie ujawnia owner UUID, payloadów ani poświadczeń.
6. Przy pierwszym uruchomieniu danej grupy/nowej partycji jawnie zaakceptuj
   granicę zatrzymanego logu:

   ```sh
   PYTHONPATH=services/api python services/api/scripts/run_checkpointed_intelligence_consumer.py \
     --broker-config /private/path/broker.json --bootstrap-retained-log
   ```

   Przy kolejnym uruchomieniu pomiń flagę. Brak stanu dla przydzielonej partycji
   daje `partition_bootstrap_required`, zamiast ukrytego resetu offsetów.
   Dodatkowy worker tej samej grupy działa przez broker rebalance i DB fencing;
   nie dodawaj równoległego przetwarzania wewnątrz pojedynczej partycji.
7. Zatrzymuj własny proces SIGTERM/SIGINT. Runner zwalnia tylko swoje lease
   i zamyka klienta. SIGKILL pozostawia owner record, który kolejny claim
   bezpiecznie zastępuje. Błąd transakcji/ACK nie pozwala czytać kolejnego
   rekordu w tym procesie; po usunięciu przyczyny uruchom go ponownie.
8. W przypadku odrzucenia sprawdź bezpieczny kod CLI. Błąd konfiguracji daje
   exit 2, odmowa checkpointu exit 3, niedostępny transport/baza exit 4.
   Raw kwarantanny jest prywatny; użyj istniejącego procesu przeglądu/replay
   z [runbooka recovery](realtime-recovery.md), zachowując oryginalny zapis.

Połączenie PostgreSQL i statement mają limit 3 s; inspekcje i odczyty metadanych
brokera mają jawne limity. Nie ma nowego publicznego endpointu telemetry,
heartbeat ani automatycznego wyznaczania zdrowia workera. Prywatna konfiguracja
jest niezależna od env konfigurującego wcześniejszy consumer.

## Weryfikacja i rollback

```sh
PYTHONPATH=services/api python -m pytest -q services/api/tests/test_intelligence_checkpoint_runner.py
PYTHONPATH=services/api REQUIRE_BROKER_TESTS=1 python -m pytest -q services/api/tests/test_intelligence_checkpoint_durability.py
```

Drugi zestaw wymaga działającego Docker i tworzy własne PostgreSQL/Redpandę
na losowych portach. Testuje realne transakcje, SIGKILL przed ACK, dwie partycje,
raw/key/nagłówki/timestamp, rollback projekcji/kwarantanny, fencing, claim podczas
transakcji i rebalance dwóch klientów. Obowiązkowe CI ustawia
`REQUIRE_BROKER_TESTS=1`; brak DB/brokera nie jest dopuszczalnym skipem.

Rollback aplikacji zachowuje wszystkie cztery tabele AI 10 i ich dane.
Checksum-pinned [plan rollbacku](application-rollback.md) oraz próby Compose
i Kubernetes obejmują rzeczywisty fixture checkpointu/transportu i pełne
odciski tabel. Fixture ma jawne mechaniczne współrzędne; nie jest dowodem
handoffu z rzeczywistego brokera. Nie wykonuj downgrade ani cleanup cudzych
kontenerów. Ten przyrost nie zamyka AI 07/08, approved head, native snapshot,
overlay/deploy, UI ani trzech rzeczywistych modeli wymaganych dla całego AI 10.
