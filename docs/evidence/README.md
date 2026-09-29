# Dowody weryfikacji

Indeks przeglądany 2026-09-29. Poniżej znajdują się ostatnie zachowane wyniki
potrzebne do opisania obecnych możliwości projektu. Każdy raport dotyczy
konkretnej daty, rewizji i środowiska; nie oznacza nowego uruchomienia na HEAD.

| Obszar | Data wykonania | Raport i zakres |
|---|---|---|
| AI 06.6b.2b — lifecycle/coverage inventory | 2026-09-29 | [Odbiór lokalny](ai/06/06.6b.2b/README.md): prywatne immutable qualified windows z parent source ID, historyczna aktywność/routing, fizyczny stream coverage i maturity; oba smoke dwukrotnie i 704 testy. Nowa publikacja03, domyślne przełączenie i model08 pozostają otwarte. |
| AI 06.6b.2a — wersjonowany source 2.7 | 2026-09-29 | [Odbiór lokalny](ai/06/06.6b.2a/README.md): 58 tabel, 46 facts/plans i 12 private truth, niezmienne source ID/config/manifest,36 bramek liczone po odczycie, oba smoke dwukrotnie. Domyślne przełączenie i nowa publikacja 03 pozostają otwarte. |
| AI 06.6b.1 — typowane tabele inventory | 2026-09-29 | [Odbiór lokalny](ai/06/06.6b.1/README.md): 27 tabel, oddzielne facts/truth, native CSV/Parquet parity, niezależne uzgodnienie procesu i projekcji na obu profilach. Kandydat tabel; domyślny source, manifesty/gates i nowa publikacja 03 pozostają otwarte. |
| AI 06.6a — realizacja koszyków źródłowych | 2026-09-29 | [Odbiór lokalny](ai/06/06.6a/README.md): sprzedaż ograniczona wspólnym stock, poprawne ceny częściowej realizacji, refund versus quality restock, causal panel/history/cohorts i uzgodnione snapshoty. Osobny kandydat; publikacja source/snapshot/curated i inventory readiness pozostają otwarte. |
| AI 03.6 — pełny cross-repo | 2026-09-29 | [Odbiór obu repo](ai/03/03.6/README.md): oba standardowe smoke dwukrotnie na Darwin/Linux, osobny późny fakt, parity/IDs/as-of, budżet oraz [publikacja na main obu repo z Required CI](ai/03/03.6/main-publication.json). Otwiera 04 i 06. |
| AI 06.3 — polityka i realizacja dostaw | 2026-09-29 | [Odbiór lokalny](ai/06/06.3/README.md): znany stock position i historia, explicit config/MOQ/cadence, idempotencja, osobna deterministyczna symulacja partial/delayed receipts oraz uzgodnienie z ledgerem. Generator 2.6 zachowuje IDs; inventory nadal false. Następny zakres 06.4. |
| AI 06.2 — dostawcy i rzeczywiste przyjęcia | 2026-09-29 | [Odbiór lokalny](ai/06/06.2/README.md): oferty, MOQ, wersje znanych terminów, partial/delayed receipts, uzgodnienie z ledgerem i oddzielna supplier truth. Generator 2.6 zachowuje IDs; inventory nadal false. |
| AI 06.1 — kontrakt ledgeru | 2026-09-29 | [Opening, ruchy, replay i adapter legacy](ai/06/06.1/README.md): lokalny odbiór oddzielnego fixture; generator 2.6 zachowuje IDs, inventory nadal false. |
| AI 03.5 — curated w repo AI | 2026-09-29 | [Odbiór lokalny](ai/03/03.5/README.md): 743 testy, typed normalization/mapping/quarantine, immutable IDs, as-of, oba smoke i truth dwukrotnie oraz odłączony wheel. |
| AI 03.4 — typed importer w repo AI | 2026-09-29 | [Odbiór lokalny](ai/03/03.4/README.md): 706 testów, oba smoke i truth dwukrotnie, atomowość/idempotencja/typed parity oraz odłączony wheel. |
| AI 03.3 — kontrakt handoff | 2026-09-28 | [Odbiór lokalny](ai/03/03.3/README.md): pełny mały fixture, wspólna wersja/schema/expected manifest, budget i niezależny checker konsumenta bez generatora. |
| AI 03.2 — niezmienny exporter | 2026-09-28 | [Odbiór lokalny](ai/03/03.2/README.md): allowlista 25 tabel, opcjonalna evaluation truth, przeliczone 46 hard gates, atomowa publikacja, checksums/parity, idempotencja i dwa przebiegi obu smoke. |
| AI 03.1 — format i artefakty | 2026-09-28 | [Odbiór lokalny](ai/03/03.1/README.md): typed Parquet wszystkich 40 tabel, porcje/partycje, polityka Git/fixture/cleanup oraz duży writer. |
| AI 11 — semantyczny RAG | 2026-09-28 | [Końcowy odbiór i publikacja w repo AI](ai/11/README.md): real Titan V2, zaliczone golden quality, użytkowa kwalifikacja/aktywacja/rollback i trwałość. Odpowiedzi i narzędzia agenta należą do 12. |
| Audyt AI 02 → AI 03 | 2026-09-28 | [Gotowość do rozpoczęcia 03](ai/02/audit/README.md): pełny fingerprint workera, historia obserwacji as-of, ponowny odbiór źródła i pełne testy na PostgreSQL. Required CI PR i push na main ma success; audyt zawiera SHA i wyniki kontroli. |
| Źródło i izolacja AI 02 / DATA-05 | 2026-09-28 | [Odbiór](ai/02/data05/README.md): source 2.6, 46 hard gates, osobne parametry symulacji, izolowany worker, powtórzenia profili, zgodne demo i archiwa 2.0–2.5. Źródło do AI 03; modele/inventory mają dalsze bramki. |
| Chronologia i zwroty AI 02 / DATA-03 | 2026-09-28 | [Odbiór lokalny](ai/02/data03/README.md): konkretne pozycje, częściowe ilości, okna kategorii/kanałów, refundacje według zapłaconej ceny i 39-dniowy ogon; siedem hard gates, dwa snapshot cutoffy, zgodne demo i odczyt source 2.0–2.3. Końcowy odbiór źródła: DATA-05. |
| Popyt, panel i koszyki AI 02 / DATA-02/03/05 | 2026-09-28 | [Odbiór lokalny](ai/02/demand-panel/README.md): pełny ważny panel i jawne statusy, jedna formuła, konserwacja sztuk i koszyki bez powtórzeń, cechy AI 3.0; 100% coverage smoke, zgodne demo. Dalsze odbiory: [zwroty](ai/02/data03/README.md); izolację truth potwierdza DATA-05. |
| Ceny i promocje AI 02 / DATA-04 | 2026-09-28 | [Odbiór lokalny](ai/02/data04/README.md): wspólny resolver, scope/known-at i rewizje, cztery typy promocji, uzgodnienie transakcji, chronologiczne pre/post truth; sześć bramek, 100% coverage cen ważnych kombinacji smoke, 543 testy. Końcowy odbiór źródła: DATA-05. |
| Wymiary i kalendarz AI 02 / DATA-02 | 2026-09-28 | [Odbiór lokalny](ai/02/data02/README.md): katalog/SKU, rozdzielone lokalizacje i kanały, wersje routing/asortyment/lifecycle, PL/DE-BE i DST, osiem hard gates, 485 testów; Pełny panel i pozostałe komponenty mają własne późniejsze odbiory. |
| Konfiguracja i identity AI 02 / DATA-01 | 2026-09-28 | [Odbiór lokalny](ai/02/data01/README.md): jawne daty/profile, manifest v2, source/feature IDs, dwukrotne smoke i temporal smoke, kontrast 100/20, zgodność demo i seeda; Końcowy odbiór źródła: DATA-05. |
| Fundament, persistence, kontrakty i lokalne auth AI 01 | 2026-09-28 | [Osobne repo AI](ai/01/README.md): 267 testów, prywatne poświadczenia i whole-scope 401/403, schemas/PIT/lineage oraz rzeczywisty HTTP z wheel na czystym checkoutcie. Osobny wcześniejszy pomiar rzeczywistego Compose: PostgreSQL/pgvector, MLflow, migracje, trwałość i DB outage/recovery. [Zdalny Required CI obu repo](ai/01/remote-ci.json): PR i push na main success, 273 testy AI, rzeczywisty Compose na Linux AMD64 i zachowana ochrona main. |
| Audyt AI 00 | 2026-09-27 | [Stan wyjściowy `cbf28b2`](ai/00/README.md): dwa `small`, kontrast 100/20, dane/ML/event/API, 138 testów, RF reload i CI źródłowego SHA. Źródło wymaga poprawek w 02. |
| Izolacja seeda | 2026-09-27 | [Próby PostgreSQL](pre-ai-00/2026-09-27-seed-isolation.md) na kodzie `667f349`: 27 testów bez DB, pięć przebiegów DB i sprzątanie po błędzie; osobny zakres wobec audytu AI 00. |
| Monitoring | 2026-09-26 | [ARM64/AMD64](observability/2026-09-26-validation.md): próbki, Grafana, pending/firing/resolution alertu; 24 zadania Required CI. |
| Jenkins | 2026-09-26 | [Rzeczywisty build](jenkins/2026-09-26-validation.md): checkout, lokalne kontrole i izolowana próba runtime; bez cloud deploy. |
| Kubernetes | 2026-09-26 | [Runtime kind](kubernetes/2026-09-26-runtime.md): NetworkPolicy, jobs, PVC, przeglądarka, restart i rollback. |
| Terraform/AWS | 2026-09-26 | [State i drift](aws/2026-09-26-state-drift.md): inwentaryzacja i plan, testy lokalnego state, backend S3/KMS bez aktywacji. |
| Rejestr i wydanie | 2026-09-26 | [GHCR v0.2.1](releases/2026-09-26-registry.md): podpisane SBOM/provenance i rollback po pobraniu digestów na świeżym runnerze. |
| Odtwarzanie bazy | 2026-09-25 | [Recovery](db/README.md): zawartość i schemat, idempotentne operacje oraz zapis po restore. |
| Lokalny rollback ARM64 | 2026-09-25 | [Próba wersjonowana](releases/README.md): zachowanie danych przy zgodnym schemacie. |
| Testy przeglądarkowe | 2026-09-25; także w późniejszych próbach CI | [Macierz E2E](e2e/README.md): siedem ścieżek Chromium i instrukcja opcjonalnych zrzutów. |
| Zależności i kontrole CI | 2026-09-25 | [Raport kontroli](github-actions/2026-09-25-validation.md): konkretne rewizje, skany i progi. Bieżący zakres pipeline opisuje [CI/CD](../guides/ci-cd.md). |
| Ochrona main | 2026-09-25 | [Ustawienia GitHub](github/README.md): zapis konfiguracji wymaganych PR i required-result. |
| Dane demonstracyjne | 2026-09-27 | [Scenariusze](data/scenario-coverage-report.md): wynik kontraktów dla wybranego zestawu danych. |
| Model Random Forest | 2026-09-27 | [Ocena i powtórzenie](ml/fixed-origin-rf-2026-09-27/README.md): RF 20/80 wobec dwóch baseline na tych samych oknach; decyzja `rejected`. Historyczny snapshot pozostaje w [indeksie ML](ml/README.md). |

Daty danych uczących nie są datami treningu. Wyniki ML sprzed poprawienia
protokołu oceny nie stanowią potwierdzenia jakości prognozy z ustalonego origin.
Aktualne ograniczenia: [ML](../guides/ml.md), [audyt](../audits/open-findings.md).

Opcjonalne nowe zrzuty można wygenerować do `frontend-api/` według instrukcji
E2E. Zakres testów opisuje raport, a nie sama obecność obrazu. Zapisuj datę
i rewizję każdego nowego capture.

Nowe surowe wyniki narzędzi trafiają do ignorowanego `ci-cd/reports/`.
Sposób promowania małego, oczyszczonego dowodu i aktualizacji tego indeksu:
[zasady dokumentacji](../guides/documentation.md).
