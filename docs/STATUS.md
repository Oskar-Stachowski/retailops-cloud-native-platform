# Aktualny status RetailOps

Aktualizacja dokumentacji i kodu: **2026-09-27**. Ostatni
[audyt przygotowań AI](evidence/pre-ai-00/2026-09-27-readiness.md) obejmuje
przegląd i 103 testy na `4da25cb` oraz
[weryfikację izolacji seeda](evidence/pre-ai-00/2026-09-27-seed-isolation.md)
na kodzie `667f349`: 27 testów bez DB, pięć przebiegów po 10 testów z DB
i próbę sprzątania po błędzie. Odczytane zielone CI dotyczy `4da25cb`;
nowsze commity lokalne mają opisaną walidację lokalną. Nie jest to nowy odbiór
pełnego runtime ani konta AWS. Zakres pozostałych prób: [indeks dowodów](evidence/README.md).

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
| ML | Lokalna generacja cech, ocena RF z trzema oknami walidacyjnymi i odłożonym testem całego horyzontu oraz zweryfikowana ścieżka artefaktu do batchu, metadanych i metryk. [Ocena z 27.09.2026](evidence/ml/fixed-origin-rf-2026-09-27/README.md) odrzuciła RF wobec średniej ruchomej; brak kwalifikacji do serving. |

## Zakres użycia

Projekt służy do lokalnego demo i weryfikacji praktyk DevOps. Przełączanie
`user_id` nie jest uwierzytelnianiem. Lokalny Compose przypina publikowane
porty do loopback zgodnie z [instrukcją](guides/local-development.md).

Nie ma potwierdzonego produkcyjnego wdrożenia AWS/EKS, produkcyjnego model serving,
MLflow, RAG ani agenta Bedrock. Te elementy opisuje wyłącznie [plan AI](plans/ai/README.md).

## Punkt wznowienia

Można rozpocząć instrukcję **AI 00**; sam etap nadal jest do wykonania.
Nie ma otwartych prac wymaganych przed jego rozpoczęciem.
[Lista przed AI 00](plans/before-ai-00.md) i [otwarte ustalenia](audits/open-findings.md)
przypisują pozostałe warunki do właściwych etapów. Historyczne wersje danych,
streaming, rzeczywiste auth i serving wymagają ich własnych bramek odbioru.
