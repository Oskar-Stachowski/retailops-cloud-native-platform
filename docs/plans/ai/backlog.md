# Najbliższe prace AI

[Fundament 01](../../evidence/ai/01/README.md) ma odbiór lokalny i zdalny:
Required CI PR oraz push na main obu repozytoriów ma success.
Główny punkt wznowienia to DATA-02 etapu 02. [DATA-01](../../evidence/ai/02/data01/README.md)
ma lokalny odbiór konfiguracji i tożsamości; etap 02 jest w realizacji.
Ten plik zawiera otwartą pracę; [audyt](../../audits/open-findings.md) opisuje
potwierdzone problemy i kryteria ich zamknięcia.

## Kolejny mały PR etapu 02

**Repo:** RetailOps. **Zależność:** konfiguracja i identity DATA-01.
Zakres DATA-02: rozdzielić selling location, stock location, channel i region;
wersjonować assignments/routing oraz lifecycle/assortment. Naprawić SKU,
rozdzielić brand/category i channel/region, dodać hierarchię produktów i
kalendarz PL/DE z flagami otwarcia. Legacy pola wyprowadzać przez adapter.
Zachować demo, manifest v2 oraz testy identity i powtarzalności.

Dalsze PR-y według [instrukcji](etapy/02-dane-sprzedazowe.md):
wspólne ceny/promocje (DATA-04), demand/panel/koszyki (DATA-02/03/05),
chronologia/zwroty (DATA-03), rozdzielenie truth i bramki (DATA-05).
Źródło pozostaje `not_ready` do AI 03 do odbioru pełnego etapu 02.

## Praca równoległa od obecnego punktu

- **RetailOps / etap 02, DATA-02:** wymiary, SKU, routing, lifecycle i kalendarz;
  potem kolejne poprawki źródła w kolejności opisanej wyżej.
- **Repo AI / etap 11, zakres 1–2:** rejestr zatwierdzonego korpusu, allowlista,
  access_class, source SHA/checksums i document_status; następnie parser/chunker
  oraz testy offline. Nie wymaga ukończenia etapu 02.
- **Opcjonalnie 16A:** projekt inputs/ownership i wariantu infrastruktury,
  walidacja oraz kosztorys po ustaleniu tych wejść; bez automatycznej zgody na apply.

Każdy strumień ma osobny branch/worktree i PR, jednego właściciela wspólnych
kontraktów oraz własne evidence. Zmiany rejestru/statusu integrujemy kolejno.
Etap 03 czeka na odbiór 02, a 04–05 na właściwe dane; agent 12 czeka na 10 i 11.
Po 03 można rozdzielić 04 i 06, po 04/05/06 — 07 i 08.

## Przypisanie warunków do etapów

| Etap | Otwarte warunki i zakres odbioru |
|---|---|
| **02 — źródło** | DATA-02–05. Pełny poprawny panel, scope/availability cen i promocji, zgodne transakcje i return tail, odrębne truth, hard gates z negatywnymi przypadkami. `inventory_ready=false`, stockout/anomaly `not_ready`. |
| **03 — snapshot/curated** | ML-07: rozwinąć manifest v2 o curated/label IDs i pełną lineage, immutable pliki i importer, schema/checksums, wersje/as-of korekt, idempotencja i kwarantanna. Pierwszy import przez pliki, bez operacyjnej DB i brokera. |
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
