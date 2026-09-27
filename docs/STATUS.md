# Aktualny status RetailOps

Przegląd dokumentacji i kodu: **2026-09-27**, punkt odniesienia
`d7e8725bfb517595d2cefda4d6011f2db70b2aed`.
Ten przegląd nie jest nowym uruchomieniem aplikacji, CI ani audytem konta AWS.
Daty, rewizje i zakres wykonanych prób podaje [indeks dowodów](evidence/README.md).

## Dostępne możliwości

| Obszar | Obecny zakres |
|---|---|
| Aplikacja lokalna | React, FastAPI, PostgreSQL, migracje i seed; widoki danych, Product 360, decyzje alertów i rekomendacji, historia operacji oraz role demonstracyjne. |
| Dane i zdarzenia | Deterministyczny generator, walidacja kontraktów, Redpanda, konsument zdarzeń i trwały model odczytu w PostgreSQL. Pełna ścieżka generator → broker → konsument wymaga osobnej weryfikacji. |
| CI i ochrona repozytorium | Required CI wybiera pełne kontrole obszarów i agreguje wynik `required-result`. Polityka `main` i jej ostatni zapis znajdują się w [governance](governance/branch-protection.md). |
| Wydania | Udokumentowane `v0.2.1`: obrazy Linux AMD64 w GHCR, podpisane provenance i SBOM, pobranie po digest oraz zgodny schematowo rollback. |
| Baza i rollback | Izolowane próby backup/restore oraz zmiany i przywrócenia wersji aplikacji; brak dowodu odwracalności dowolnych migracji schematu. |
| Kubernetes | Lokalny kind na ARM64/AMD64: ingress, NetworkPolicy, jobs, PVC, testy przeglądarkowe, restart i rollback. Ścieżka używa lokalnie budowanych obrazów. |
| Terraform | Kod fundamentu AWS, kontrolowany plan/drift i przygotowany backend S3/KMS. Ostatni spis z 2026-09-26 nie znalazł pasującego wdrożenia ani bucketu state; rola OIDC do planu była obecna. |
| Monitoring | Metryki API/DB/stream, Prometheus, Grafana i próba rzeczywistego firing/resolution alertu. SLO dotyczy scrape metryk; brak dowodu dostępności żądań użytkownika przez 30 dni i dostarczania powiadomień. |
| Jenkins | Rzeczywiste lokalne wykonanie pipeline z 2026-09-26; dodatkowa walidacja, bez wdrażania do chmury. |
| ML | Lokalna generacja cech, średnia ruchoma, Random Forest, ewaluacja, batch i metadane. Obecny protokół wymaga poprawy dostępności cech w czasie i zasad dopuszczania modeli. |

## Zakres użycia

Projekt służy do lokalnego demo i weryfikacji praktyk DevOps. Przełączanie
`user_id` nie jest uwierzytelnianiem. Przy uruchamianiu używaj loopback zgodnie
z [instrukcją](guides/local-development.md).

Nie ma potwierdzonego produkcyjnego wdrożenia AWS/EKS, produkcyjnego model serving,
MLflow, RAG ani agenta Bedrock. Te elementy opisuje wyłącznie [plan AI](plans/ai/README.md).

## Punkt wznowienia

Najbliższy zaplanowany obszar to [poprawa oceny ML](plans/ml-evaluation.md),
zaczynając od kontraktu dostępności cech w momencie prognozy.
[Audyt](audits/open-findings.md) zawiera także nadal otwarte problemy aplikacji
i narzędzi operacyjnych wraz z kryteriami weryfikacji poprawek.
