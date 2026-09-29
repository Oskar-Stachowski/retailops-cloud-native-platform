# Najbliższe prace AI

[Odbiór 03](../../evidence/ai/03/03.6/README.md) obejmuje pełną ścieżkę
generator → kwalifikacja → eksport → import → curated na przypiętych rewizjach,
oba smoke dwukrotnie i Required CI obu repo. Pierwsza ścieżka używa plików;
forecast source jest gotowy przy inventory false. AI 03 jest na main obu repo;
[zapis publikacji](../../evidence/ai/03/03.6/main-publication.json) podaje commity i CI.
Ten plik zawiera wyłącznie otwartą pracę; [audyt](../../audits/open-findings.md)
opisuje potwierdzone problemy i kryteria ich zamknięcia.

## Następny zakres — AI 04

**Repo:** AI-intelligence. **Wejście:** odebrany source 2.6, snapshot/handoff 1.0
i curated 1.0 z [karty danych](../../evidence/ai/03/03.6/dataset-card.md).
[Instrukcja 04](etapy/04-forecasting.md) zaczyna od kanonicznego panelu,
cech znanych w origin i jawnych splitów. Następnie baseline/RF/HGB mają wspólne
rekordy oceny, zamrożony test i politykę dopuszczenia. Inventory features są
wyłączone; target opisuje obserwowaną sprzedaż.

## Praca równoległa od obecnego punktu

- **Repo RetailOps / AI 06.6b.2b:** kwalifikacja lifecycle/coverage source 2.7
  i dojrzałych okien 08. Następnie 06.6b.2c: rozszerzony eksport/import/curated 03,
  przełączenie domyślnego source, pełne gates cross-repo i zależne oceny04/05.
- **Repo AI / przygotowanie 12:** interfejsy narzędzi read-only, graf i test doubles,
  limity, freshness i audyt. [RAG 11](../../evidence/ai/11/README.md) jest odebrany;
  pełne narzędzia, odpowiedzi i integracja użytkowa wymagają również 10.
- **Opcjonalnie 16A:** projekt inputs/ownership i infrastruktury, walidacja
  oraz kosztorys po ustaleniu wejść; bez automatycznej zgody na apply.

Każdy strumień ma osobny branch/worktree i PR, jednego właściciela wspólnych
kontraktów oraz własne evidence. Zmiany rejestru/statusu integrujemy kolejno.
Po 04 można rozpocząć 05 bez oczekiwania na ledger 06. Po zgodnym odbiorze
04/05/06 można rozdzielić 07 i 08.
Pełne przypisanie repozytoriów i kolejność: [pisemna mapa etapów](kolejnosc-i-repozytoria.md).

## Przypisanie warunków do etapów

| Etap | Otwarte warunki i zakres odbioru |
|---|---|
| **04 — forecasting** | Użyć poprawnego panelu i kalendarza, znanych w origin cech i nowego snapshotu; wspólne rekordy baseline/RF/HGB, zamrożony test i polityka. Przenieść istniejące poprawne mechanizmy, nie przywracać dawnych lagów po wierszach ani target covariates. |
| **05 — MLflow i serving** | Zachować rejected/failed i pełną lineage. Własny batch worker, atomic complete output, API z właściwym grain, test crash/retry/rollback; obecny RF `rejected` nie jest championem. |
| **06 — inventory** | 06.6b.2b: lifecycle/coverage source 2.7; 06.6b.2c: exporter/importer/curated 03 i przełączenie domyślnej ścieżki AI, pełne gates DATA-06; zgodne oceny04/05. |
| **07 — anomaly/DQ** | Po bramkach źródła i ledgeru: oddzielne scenariusze truth i dojrzałe labels, dojrzałe okna, baseline i oceniony detektor. Scenariusze demo nie zastępują oceny. |
| **08 — stockout** | DATA-06 + poprawne upstream forecast lineage. Przyszły epizod oddzielony od aktualnego braku; labels po oknie, kalibracja i progi, jawne insufficient/stale. |
| **09 — TensorFlow** | Challenger na tych samych kwalifikujących się danych/splitach; ocena trzech zastosowań i odporności. Nie musi wygrać. |
| **10 — integracja** | OPS-03/07: jeden wykonywalny kontrakt, snapshot/version-aware event identity, legacy v1 oraz nowe intelligence.v2, trwałe ACK/kwarantanna, inbox/outbox, dedup/replay. Domenowe projekcje wyników, zgodne API/UI i rzeczywiste auth/scope. Testy z brokerem i awariami wymagane przed odbiorem. |
| **12 — agent** | Po 10/11: narzędzia read-only z auth, limitami, freshness i audytem; bez domyślnego demo-admin i mutacji operacyjnych. |
| **13 — monitoring/security** | Własne SLO AI, performance drift z dojrzałymi etykietami, telemetry, incident/security gates; lokalne testy 00 ich nie odbierają. |
| **14–15 — kind/release** | OPS-06 dla istniejących obrazów/workflow; AI Helm, persistence/migracje, NetworkPolicy, CI/GitOps, niezmienne releasy i rzeczywisty rollback. |
| **16 — AWS** | 16A: projekt i walidacja dla uzgodnionego scope, właściwy root Terraform. 16B: odrębnie zlecony pokaz, budżet, evidence i cleanup. Bez cloud apply w ramach audytu. |

K1 kończy się po 00–05. Pełny procurement, ledger i streaming nie są warunkiem
pierwszej prognozy **obserwowanej sprzedaży** bez cech inventory. Stockout/anomaly
oraz integracja mają własne późniejsze bramki; ich ograniczeń nie wolno ukrywać
przez deklarację gotowości całego AI.
