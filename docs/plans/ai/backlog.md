# Najbliższe prace AI

[Fundament 01](../../evidence/ai/01/README.md) ma odbiór lokalny i zdalny:
Required CI PR oraz push na main obu repozytoriów ma success.
Główny punkt wznowienia to [AI 03 — snapshot i curated](etapy/03-snapshot-curated.md).
[Odbiór źródła 02](../../evidence/ai/02/data05/README.md) obejmuje identity,
wymiary/kalendarz, ceny/promocje, pełny panel/koszyki, chronologię/zwroty,
separację symulacji oraz rzeczywisty worker bez dostępu do truth.
Ten plik zawiera otwartą pracę; [audyt](../../audits/open-findings.md) opisuje
potwierdzone problemy i kryteria ich zamknięcia.

## Kolejny mały PR etapu 03

**Repo:** RetailOps. **Zależność:** odebrane źródło 2.6 i bramki forecast-source.
**03.3 — kontrakt handoff.** Przygotować jeden mały, samowystarczalny fixture
na podstawie [eksportera 03.2](../../reference/ai-snapshots.md), schemas i expected
manifest. Opisać grain, mapping, time semantics, wersje, date ranges i readiness.
Zmiany upstream/consumer mają osobne commity/PR-y i wspólną wersję kontraktu.
Fixture i archiwa regresji łącznie muszą mieścić się w limicie 5 MiB po rozpakowaniu.
Następnie 03.4 importer, 03.5 curated i 03.6 bramka cross-repo.
Nie kopiować generatora do repo AI; odbiór cross-repo następuje po kontrakcie,
importerze i curated builderze. Zachować istniejące wersje ilości i odczyt as-of.

## Praca równoległa od obecnego punktu

- **RetailOps / etap 03:** handoff fixture; [03.2](../../evidence/ai/03/03.2/README.md) ma lokalny odbiór eksportera. Publikacja 03.1/03.2 i zdalne Required CI pozostają do wykonania.
- **Repo AI / pozostały zakres 11:** rzeczywisty provider embeddings,
  użytkowa kwalifikacja/aktywacja i odbiór jakości na zatwierdzonym golden set.
  [Fundament offline](../../evidence/ai/11/README.md) obejmuje już korpus,
  chunker, pgvector, retrieval, testowy lifecycle i administracyjne runy.
  Integrację real embeddings skoordynować z 12; nie obniżać progów dla fake.
- **Opcjonalnie 16A:** projekt inputs/ownership i wariantu infrastruktury,
  walidacja oraz kosztorys po ustaleniu tych wejść; bez automatycznej zgody na apply.

Każdy strumień ma osobny branch/worktree i PR, jednego właściciela wspólnych
kontraktów oraz własne evidence. Zmiany rejestru/statusu integrujemy kolejno.
Etap 03 ma spełnioną lokalną i zdalną bramkę źródła; 04–05 czekają na właściwe snapshoty,
a agent 12 na 10 i 11.
Po 03 można rozdzielić 04 i 06, po 04/05/06 — 07 i 08.
Pełne przypisanie repozytoriów i kolejność: [pisemna mapa etapów](kolejnosc-i-repozytoria.md).

## Przypisanie warunków do etapów

| Etap | Otwarte warunki i zakres odbioru |
|---|---|
| **03 — snapshot/curated** | Rozwinąć manifest v2 o curated/label IDs i pełną lineage, immutable pliki i importer, schema/checksums, wersje/as-of korekt, idempotencja i kwarantanna. Pierwszy import przez pliki, bez operacyjnej DB i brokera. |
| **04 — forecasting** | Użyć poprawnego panelu i kalendarza, znanych w origin cech i nowego snapshotu; wspólne rekordy baseline/RF/HGB, zamrożony test i polityka. Przenieść istniejące poprawne mechanizmy, nie przywracać dawnych lagów po wierszach ani target covariates. |
| **05 — MLflow i serving** | Zachować rejected/failed i pełną lineage. Własny batch worker, atomic complete output, API z właściwym grain, test crash/retry/rollback; obecny RF `rejected` nie jest championem. |
| **06 — inventory** | DATA-06: jedno otwarcie, uzgodnienie ruchów, physical stock location i historyczny fulfillment mapping. Nowa wersja danych i ponowienie importu/ocen zależnych od zapasu. |
| **07 — anomaly/DQ** | Po bramkach źródła i ledgeru: oddzielne scenariusze truth i dojrzałe labels, dojrzałe okna, baseline i oceniony detektor. Scenariusze demo nie zastępują oceny. |
| **08 — stockout** | DATA-06 + poprawne upstream forecast lineage. Przyszły epizod oddzielony od aktualnego braku; labels po oknie, kalibracja i progi, jawne insufficient/stale. |
| **09 — TensorFlow** | Challenger na tych samych kwalifikujących się danych/splitach; ocena trzech zastosowań i odporności. Nie musi wygrać. |
| **10 — integracja** | OPS-03/07: jeden wykonywalny kontrakt, snapshot/version-aware event identity, legacy v1 oraz nowe intelligence.v2, trwałe ACK/kwarantanna, inbox/outbox, dedup/replay. Domenowe projekcje wyników, zgodne API/UI i rzeczywiste auth/scope. Testy z brokerem i awariami wymagane przed odbiorem. |
| **11 — RAG** | Ścieżka rzeczywistego providera w build/query i kontraktach, użytkowa kwalifikacja/aktywacja/rollback oraz zaliczone progi jakości. Zgody na obecny korpus i 44 pytania zapisano; fake nie otwiera aktywacji. |
| **12 — agent** | Po 10/11: narzędzia read-only z auth, limitami, freshness i audytem; bez domyślnego demo-admin i mutacji operacyjnych. |
| **13 — monitoring/security** | Własne SLO AI, performance drift z dojrzałymi etykietami, telemetry, incident/security gates; lokalne testy 00 ich nie odbierają. |
| **14–15 — kind/release** | OPS-06 dla istniejących obrazów/workflow; AI Helm, persistence/migracje, NetworkPolicy, CI/GitOps, niezmienne releasy i rzeczywisty rollback. |
| **16 — AWS** | 16A: projekt i walidacja dla uzgodnionego scope, właściwy root Terraform. 16B: odrębnie zlecony pokaz, budżet, evidence i cleanup. Bez cloud apply w ramach audytu. |

K1 kończy się po 00–05. Pełny procurement, ledger i streaming nie są warunkiem
pierwszej prognozy **obserwowanej sprzedaży** bez cech inventory. Stockout/anomaly
oraz integracja mają własne późniejsze bramki; ich ograniczeń nie wolno ukrywać
przez deklarację gotowości całego AI.
