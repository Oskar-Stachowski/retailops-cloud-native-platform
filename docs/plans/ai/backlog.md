# Najbliższe prace po audycie AI 00

Baza: [pomiary na `cbf28b2`](../../evidence/ai/00/README.md), 27.09.2026.
**Etap 01 w realizacji; następny zakres: persistence, migracje i Compose.**
[Pakiet i bazowy HTTP](../../evidence/ai/01/README.md) działają w osobnym
lokalnym repo `retailops-ai-intelligence`.
Ten plik zawiera otwartą pracę, a [audyt](../../audits/open-findings.md)
dowody błędów i kryteria ich zamknięcia. Etap 01 pozostaje częściowy, 02–17 są planowane;
brak nowej funkcji z planu nie jest sam w sobie błędem istniejącego demo.

## Następny mały PR etapu 01

**Repo:** osobne `retailops-ai-intelligence` obok RetailOps, branch
`ai/implementation`. HTTP: `e6c7888`; dowody czystego checkoutu/wheel: `7d67530`.
Bieżące możliwości i uruchomienie opisują `docs/STATUS.md` oraz
`docs/http-service.md` w repo AI. Repo pozostaje lokalne.

Zakres: PostgreSQL dla AI, oddzielna baza i użytkownik MLflow, jawne migracje
Alembic oraz lokalny Compose API/Postgres/MLflow z trwałymi wolumenami.
Zarejestruj rzeczywistą sondę DB w mechanizmie readiness; obecna rola foundation
sprawdza tylko startup i nie potwierdza gotowości bazy ani predykcji.

**Odbiór tego PR:**

- Własność i uprawnienia AI/MLflow są rozdzielone od operacyjnej bazy RetailOps.
  Metadata i duże artefakty mają jawne miejsca zapisu; sekrety są poza Git/logami.
- Migracje mają wersję, są uruchamiane jawnie i nie konkurują ze startem każdego
  procesu API. Nie zastępuj ich samym create_all przy uruchomieniu serwera.
- Rzeczywiste `make compose-up/compose-down` uruchamiają i zatrzymują usługi.
  Porty hosta pozostają lokalne; zasady bind/Host są świadomie dostosowane
  do kontrolowanej sieci Compose. Nie powstaje drugi broker RetailOps.
- Zapisane dane przetrwają restart usług. Odłączenie rzeczywistej DB pogarsza
  readiness do 503, health pozostaje 200, a po powrocie DB gotowość wraca.
  Raport rozróżnia provider fakes od prób rzeczywistych usług.
- Konfiguracja, migracje, Compose i nowe testy wchodzą do wymaganych kontroli.
  Instrukcja obejmuje pierwsze uruchomienie, migrację i bezpieczne zatrzymanie;
  usunięcie wolumenów nie jest domyślnym shutdown.

Pozostała część **tego samego etapu 01**: wykonywalne wersje kontraktów
dataset/feature/label/prediction/run/tool oraz uprawnienia pierwszych endpointów
aplikacyjnych. Obecny token metryk nie jest systemem tożsamości użytkowników AI.
Po publikacji repo należy wykonać zdalne CI i ustawić ochronę gałęzi z wymaganym
`required-result`; lokalna walidacja workflow nie potwierdza tych ustawień.
Cały etap 01 pozostaje otwarty.

## Pierwszy mały PR etapu 02

**Repo:** RetailOps. **Zależność:** odbiór 01 i uzgodnione wersje kontraktów.
Zakres DATA-01: jedno rozwiązanie requested/effective config, jawne daty i manifest v2
obok v1, wersje generatora/kalendarza/konfiguracji, source identity oraz checksumy.
Powiązać nowe feature ID z treścią źródła i kontraktem cech, zamiast wyłącznie profilem/datami/seedem.
Nie zmieniać w tym PR formuły popytu, cen, koszyków ani legacy demo.

**Odbiór tego PR:**

- Powtórzenie tych samych wejść w dwóch katalogach daje ten sam logical source/feature
  ID i treść; ścieżka venv/outputu oraz czas zapisu nie wchodzą do tożsamości logicznej.
- `small/seed42` dla 100 i 20 produktów daje różne ID. Zmiana seeda, dat, treści
  lub semantycznej konfiguracji zmienia właściwy ID; raw byte checksums są odrębne.
- Żaden efektywny parametr nie pozostaje `null`; manifest jawnie zapisuje wartości
  domyślne i override, wersje, provenance kodu i zależności.
- Zakresy per tabela obejmują rzeczywiste zwroty, promocje, plany cen i forecasty.
  Rozróżnić sprzedaż, plan i return tail; watermark ma zdefiniowane znaczenie,
  nie jest równy automatycznie największej przyszłej dacie.
- Testy istniejących kontraktów v1/demo/seed przechodzą, 19 śledzonych plików demo
  nie jest nadpisywanych. Uszkodzona treść/checksum i niekompletna konfiguracja
  manifestu v2 są odrzucane. Raport nie nazywa jeszcze źródła gotowym do AI 03.

Kolejne PR-y 02 zgodnie z [instrukcją](etapy/02-dane-sprzedazowe.md):
wymiary/lifecycle (DATA-02), wspólne ceny/promocje (DATA-04), demand/panel/koszyki
(DATA-02/03/05), chronologia/zwroty (DATA-03), rozdzielenie truth i bramki (DATA-05).

## Przypisanie warunków do etapów

| Etap | Otwarte warunki i zakres odbioru |
|---|---|
| **02 — źródło** | DATA-01–05. Pełny poprawny panel, scope/availability cen i promocji, zgodne transakcje i return tail, odrębne truth, hard gates z negatywnymi przypadkami. `inventory_ready=false`, stockout/anomaly `not_ready`. |
| **03 — snapshot/curated** | DATA-01 + ML-07: niezależne source/curated/feature/label IDs, immutable pliki i importer, schema/checksums, wersje/as-of korekt, idempotencja i kwarantanna. Pierwszy import przez pliki, bez operacyjnej DB i brokera. |
| **04 — forecasting** | ML-07 jako warunek wejść. Użyć poprawnego panelu i kalendarza, znanych w origin cech i nowego snapshotu; wspólne rekordy baseline/RF/HGB, zamrożony test i polityka. Przenieść istniejące poprawne mechanizmy, nie przywracać dawnych lagów po wierszach ani target covariates. |
| **05 — MLflow i serving** | Zachować rejected/failed i pełną lineage. Własny batch worker, atomic complete output, API z właściwym grain, test crash/retry/rollback; obecny RF `rejected` nie jest championem. |
| **06 — inventory** | DATA-06: jedno otwarcie, uzgodnienie ruchów, physical stock location i historyczny fulfillment mapping. Nowa wersja danych i ponowienie importu/ocen zależnych od zapasu. |
| **07 — anomaly/DQ** | Po bramkach źródła i ledgeru: oddzielne truth/labels (DATA-05), dojrzałe okna, baseline i oceniony detektor. Scenariusze demo nie zastępują oceny. |
| **08 — stockout** | DATA-06 + poprawne upstream forecast lineage. Przyszły epizod oddzielony od aktualnego braku; labels po oknie, kalibracja i progi, jawne insufficient/stale. |
| **09 — TensorFlow** | Challenger na tych samych kwalifikujących się danych/splitach; ocena trzech zastosowań i odporności. Nie musi wygrać. |
| **10 — integracja** | OPS-03/07: jeden wykonywalny kontrakt, snapshot/version-aware event identity, legacy v1 oraz nowe intelligence.v2, trwałe ACK/kwarantanna, inbox/outbox, dedup/replay. Domenowe projekcje wyników, zgodne API/UI i rzeczywiste auth/scope. Testy z brokerem i awariami wymagane przed odbiorem. |
| **11 — RAG** | Po 01: zatwierdzony wersjonowany korpus, access metadata, cytowania i ocena retrieval; aktualne evidence może być źródłem po zatwierdzeniu zakresu. |
| **12 — agent** | Po 10/11: narzędzia read-only z auth, limitami, freshness i audytem; bez domyślnego demo-admin i mutacji operacyjnych. |
| **13 — monitoring/security** | Własne SLO AI, performance drift z dojrzałymi etykietami, telemetry, incident/security gates; lokalne testy 00 ich nie odbierają. |
| **14–15 — kind/release** | OPS-06 dla istniejących obrazów/workflow; AI Helm, persistence/migracje, NetworkPolicy, CI/GitOps, niezmienne releasy i rzeczywisty rollback. |
| **16 — AWS** | 16A: projekt i walidacja dla uzgodnionego scope, właściwy root Terraform. 16B: odrębnie zlecony pokaz, budżet, evidence i cleanup. Bez cloud apply w ramach audytu. |

K1 kończy się po 00–05. Pełny procurement, ledger i streaming nie są warunkiem
pierwszej prognozy **obserwowanej sprzedaży** bez cech inventory. Stockout/anomaly
oraz integracja mają własne późniejsze bramki; ich ograniczeń nie wolno ukrywać
przez deklarację gotowości całego AI.
