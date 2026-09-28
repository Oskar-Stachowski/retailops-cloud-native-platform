# Dowody weryfikacji

Indeks przeglądany 2026-09-28. Poniżej znajdują się ostatnie zachowane wyniki
potrzebne do opisania obecnych możliwości projektu. Każdy raport dotyczy
konkretnej daty, rewizji i środowiska; nie oznacza nowego uruchomienia na HEAD.

| Obszar | Data wykonania | Raport i zakres |
|---|---|---|
| Fundament, persistence i kontrakty AI 01 | 2026-09-28 | [Osobne repo AI](ai/01/README.md): 208 testów, schemas/PIT/lineage i wheel na czystym checkoutcie. Osobny wcześniejszy pomiar rzeczywistego Compose: PostgreSQL/pgvector, MLflow, migracje, trwałość i DB outage/recovery. CI nowych commitów czeka na push. |
| Audyt AI 00 | 2026-09-27 | [Stan wyjściowy `cbf28b2`](ai/00/README.md): dwa `small`, kontrast 100/20, dane/ML/event/API, 138 testów, RF reload i CI źródłowego SHA. Następny etap 01; źródło wymaga poprawek w 02. |
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
