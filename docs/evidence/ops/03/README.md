# OPS-03 — trwała granica przetwarzania i ACK

Pomiar lokalny: **2026-09-30**, Darwin ARM64, Python 3.11, przypięte
PostgreSQL 16 i Redpanda 25.3.6 w izolowanych kontenerach Docker.
Baza zmian: `d4ee7a4e4217a59871c654f204f16de74017d13b` (odbiór OPS-07).
Dokładne wyniki, test cases i SHA-256 plików runtime zawiera
[local-verification.json](local-verification.json).

## Zachowanie

Runner ACK-uje synchronicznie tylko `processed`/`ignored_duplicate` po
trwałej transakcji albo potwierdzony zapis surowej wiadomości w kwarantannie.
DB/handler/quarantine/commit failure kończy proces przed następnym poll;
nie ma późniejszego commit, który przeskoczyłby lukę partycji.
Automatyczne commit i offset store są wyłączone.

Event log, metryki i marker `processed` są atomowe, z advisory lock po UUID.
Validation/decode failure zachowuje exact value/key/headers w base64,
timestamp i group/topic/partition/offset w `realtime_event_log`.
Transportowe UUID są osobne od niezweryfikowanych event IDs, a zapis raw
jest niezmienny. JSON Schema wymaga UUID zgodnego z kolumną PostgreSQL
i rezerwuje source wpisów kwarantanny.

Kontrolowany replay przypina poprawkę/operatora przed publikacją, czeka
na delivery receipt i zachowuje oryginał. Powtórzenie po przerwie DB między
dostarczeniem a receipt może dać drugą dostawę; dedup po event ID chroni metryki.
Inna poprawka dla przypiętego intent jest odrzucana.

## Odbiór

[Real-broker suite](../../../../services/api/tests/test_realtime_durability.py)
korzysta z rzeczywistego runnera, klientów Confluent, PostgreSQL i Redpandy.
Sprawdza invalid JSON/UTF-8/tombstone/envelope/payload/version/UUID/source,
byte-exact raw po restarcie DB i brokera, handler failure bez pominięcia późniejszego
offsetu, rollback częściowej projekcji, DB/quarantine outage i ponowienie,
SIGKILL po trwałym zapisie przed ACK dla poprawnego i błędnego komunikatu
oraz reviewed replay z awarią zapisu receipt i bez drugiego wkładu w metryki.

Testy jednostkowe sprawdzają także fail-stop na nieznanym wyniku, błąd commit
partycji, zamknięcie klienta po awarii stanu, blokadę replay bez delivery receipt
i niezgodny topic. API Required CI ustawia `REQUIRE_BROKER_TESTS=1`, więc brak
brokera lub nieudana próba nie może być zastąpiona pominięciem.
Pełna regresja na `da868d1`: **1424 passed, 40 skipped** (istniejące seeded DB tests).
Po ograniczeniu diagnostyki do bezpiecznego schema reason: **61 focused tests
i ponowne 17 real-broker cases passed**. Diagnostyka nie kopiuje untrusted
payloadu/typu/wersji do podsumowania kwarantanny lub stanu API.
Kontrole lokalne obejmują pełną regresję API/danych, Ruff check/format,
mypy, Bandit, walidację kontraktów, obraz API i komendę CLI w kontenerze.
Gitleaks wykazał false positive publicznego SHA-256 `.github/workflows/api-ci.yml`
w raporcie. Wyjątek wymaga jednocześnie dokładnej ścieżki raportu i tej jednej
sumy; nie pomija pliku ani reguły. Lokalny skan historii brancha przechodzi.

## Granice

Jest to at-least-once transport i idempotentna transakcja obecnych live metrics.
Kwarantanna używa PostgreSQL; topic `retailops.dlq.v1` nie jest automatycznie
publisherem tych raw records. Własne efekty zewnętrzne handlera wymagają własnej
idempotencji. Istniejące historyczne failure records nie zyskują raw wstecz.
Schema bazy i granica istniejącego same-history rollback nie zmieniają się.
Business-key revisions, AI v2, domenowe inbox/outbox, checkpoint snapshot/replay
i pełny cross-repo E2E mają dalszy odbiór AI 10.

[Runbook awarii i odtwarzania](../../../runbooks/realtime-recovery.md)
podaje komendy operatora i odtworzenia testów. Wyniki CI konkretnego PR/merge
sprawdzaj dla jego SHA w
[Required CI](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/actions/workflows/required-ci.yml).
