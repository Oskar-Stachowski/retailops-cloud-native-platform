# Awaria konsumenta i odtwarzanie wiadomości

Dotyczy obecnego konsumenta legacy v1 oraz projekcji live metrics RetailOps.
Wymaga bazy po istniejących migracjach, dostępu operatora do PostgreSQL i
`RETAILOPS_BROKER_BOOTSTRAP_SERVERS` wskazującego właściwy broker.
Polecenia poniżej uruchamiaj z katalogu głównego projektu.

## ACK i ponowienie po awarii

Automatyczny commit i automatyczny offset store są wyłączone. Runner przetwarza
wiadomości kolejno. Synchroniczny ACK następuje dopiero po zakończeniu
transakcji event log + metryki albo po potwierdzonym zapisie kwarantanny.
Błąd DB, handlera, kwarantanny lub commit zatrzymuje proces, więc wyższy
offset tej samej partycji nie może pominąć nieobsłużonej wiadomości.

1. Sprawdź stan DB/brokera i log zakończenia konsumenta. Powód błędu jest
   zachowany w stanie konsumenta, jeśli baza była dostępna.
2. Napraw zależność lub handler. Nie resetuj offsetów grupy ponad problematyczny
   komunikat. Handler operacyjny nie jest automatycznie klasyfikowany jako poison.
3. Wznów ten sam konsument i group ID. Compose/Kubernetes mogą restartować
   proces zgodnie z ich polityką; manualny entrypoint to `make realtime-consumer`.
4. Sprawdź `/dashboard/live-operations`, `/metrics` i nowe logi. Przy przerwaniu
   po zapisie DB, a przed ACK, marker `processed` chroni metryki przed ponownym wkładem.

Blokada advisory w transakcji serializuje równoczesne dostarczenia tego samego
UUID. Nieudana transakcja nie pozostawia częściowych metryk. Efekty zewnętrzne
niestandardowego handlera wymagają jego własnej idempotencji; domyślne handlery
obecnego konsumenta nie wykonują efektów zewnętrznych.

## Trwała kwarantanna

Błędny JSON, UTF-8, tombstone, nieprawidłowy envelope/payload lub wersja trafiają
do istniejącego `realtime_event_log` jako `transport_rejected`, source
`retailops.consumer.quarantine`, status `failed_dead_lettered`. UUID tego wpisu
wynika z group/topic/partition/offset. Nie zależy od niezweryfikowanego event ID.
Payload zachowuje surowe value/key/headers w base64, timestamp i pozycję transportu.
Pierwszy raw record i powód są zachowane przy ponowieniu. Source kwarantanny
jest zarezerwowany i odrzucany w zewnętrznym envelope.

Historyczny status `failed_dead_lettered` sprzed tej implementacji nie gwarantuje
zachowania raw. Taki wpis wymaga osobnego przeglądu i odczytu oryginału z brokera,
jeśli wiadomość jest jeszcze w jego retencji.

Jest to mechanizm odtwarzania w PostgreSQL. Istniejący topic `retailops.dlq.v1`
nie otrzymuje automatycznie tych wiadomości. Nie usuwaj wpisów oczekujących na
przegląd. Nowe wdrożenie używa jednej konfiguracji brokera; przy zastąpieniu
klastra lub odtworzeniu topicu uzgodnij nowe group ID i checkpointy, ponieważ
pozycje nowego logu nie identyfikują wiadomości starego klastra.

```bash
PYTHONPATH=services/api services/api/.venv/bin/python \
  services/api/scripts/realtime_quarantine.py list --limit 100

PYTHONPATH=services/api services/api/.venv/bin/python \
  services/api/scripts/realtime_quarantine.py show --id '<UUID wpisu>'
```

`show` zwraca także original raw w base64; wynik może zawierać dane operacyjne.
Polecenia nie wymagają ani nie zapisują poświadczeń w Git.

## Przejrzana poprawka i replay

1. Odczytaj raw i powód. Przygotuj `correction.json` zgodny z
   [kontraktem v1](../reference/events.md), z tematem oryginalnej wiadomości.
   Zachowaj wiarygodny oryginalny UUID; jeśli go nie było, nadaj poprawce jeden
   stabilny UUID. Replay tej poprawki zawsze używa tego samego ID i payloadu.
2. Sprawdź wartości biznesowe i zawartość korekty przed wysyłką.
3. Uruchom jawnie z nazwą operatora:

```bash
PYTHONPATH=services/api services/api/.venv/bin/python \
  services/api/scripts/realtime_quarantine.py replay \
  --id '<UUID wpisu>' --event-file /private/tmp/correction.json --operator '<operator>'
```

Korekta i operator są przypinane w DB przed publikacją. Następnie publisher
czeka na potwierdzenie brokera i zapisuje partycję/offset dostarczenia. Oryginalne
bajty i reason pozostają zachowane. `replayed` oznacza dostarczenie do brokera;
sprawdź osobno `processed` poprawionego event ID w bazie/projekcji.

Jeśli nie ma potwierdzenia brokera, intent pozostaje oczekujący. Jeśli broker
przyjął korektę, lecz zapis receipt w DB nie powiódł się, ponów tę samą komendę
z identycznym plikiem. Możliwa jest druga dostawa, którą konsument deduplikuje
po event ID. Inny payload/UUID dla już przypiętego intent jest odrzucany.
Po zapisanym receipt kolejne wywołanie zwraca `already_replayed` i nie wysyła
ponownie. `list` pomija wpisy z receipt; `show` nadal udostępnia pełen zapis.

## Odtworzenie testów

```bash
PYTHONPATH=services/api:. REQUIRE_BROKER_TESTS=1 \
  services/api/.venv/bin/python -m pytest -q \
  services/api/tests/test_realtime_durability.py
```

Test tworzy własne kontenery PostgreSQL/Redpanda z przypiętych obrazów, migruje
pustą bazę, używa losowych nazw i portów loopback oraz sprząta wyłącznie swoje
kontenery i wolumeny. API Required CI wymaga tych samych testów. Dowody i zakres:
[odbiór OPS-03](../evidence/ops/03/README.md).
