# Aktualny status RetailOps

Aktualizacja: **2026-09-28**. [Audyt AI 00](evidence/ai/00/README.md) na
`cbf28b2` obejmuje dwukrotną generację `small`, kontrast 100/20 produktów,
pomiary danych i kontraktów, **138 testów bez pominięć** oraz ponowny odczyt
ocenionych artefaktów RF. Required CI tego SHA ma `success`.
To lokalny audyt z próbami błędów na mockach DB/brokera, bez nowego odbioru
pełnego runtime ani AWS. Odrębna [weryfikacja izolacji seeda](evidence/pre-ai-00/2026-09-27-seed-isolation.md)
zachowuje dowód prób PostgreSQL. Pozostałe zakresy: [indeks dowodów](evidence/README.md).

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
| Rozbudowa AI | [Fundament AI 01](evidence/ai/01/README.md) w osobnym repo: pakiet/CLI, HTTP/telemetry, PostgreSQL/pgvector, oddzielny MLflow i jawne migracje. Kontrakty danych/run/tool, walidacja offline i lokalne uprawnienia API: 267 testów na czystym checkoutcie oraz rzeczywisty HTTP z wheel poza źródłami. Principal pochodzi z prywatnych poświadczeń, cały scope jest egzekwowany; admin nie dziedziczy odczytów. Osobny wcześniejszy pomiar Compose: crash, trwałość, awaria DB i recovery. Etap 01 ma odbiór lokalny i zdalny: Required CI PR oraz push na main obu repo przechodzi, w tym persistence na Linux AMD64; dodatkowe testy bramki CI zwiększają zestaw do 273 testów. Zmiana grants/revoked wymaga restartu API; nie ma OIDC/production IAM lub serving. Źródło 2.6 ma lokalny i zdalny odbiór AI 02; snapshot/importer AI 03 pozostają kolejnym zakresem. |

## Zakres użycia

Projekt służy do lokalnego demo i weryfikacji praktyk DevOps. Przełączanie
`user_id` nie jest uwierzytelnianiem. Lokalny Compose przypina publikowane
porty do loopback zgodnie z [instrukcją](guides/local-development.md).

Działa lokalny MLflow w repo AI. Nie ma potwierdzonego produkcyjnego wdrożenia
AWS/EKS ani produkcyjnego model serving lub agenta Bedrock. Lokalny RAG ma
[odbiór AI 11](evidence/ai/11/README.md). Dalsze wdrożenia
opisuje [plan AI](plans/ai/README.md).

## Punkt wznowienia

[Audyt AI 02](evidence/ai/02/audit/README.md), Required CI PR i push na main
potwierdzają gotowość źródła do
**[AI 03 — snapshot, importer i curated](plans/ai/etapy/03-snapshot-curated.md)**.
Źródło 2.6 przechodzi 46 hard gates; cechy AI 3.1 powstają w izolowanym workerze
z czterech projekcji faktów. Fingerprint obejmuje cały wykonywany kod, a wersje
obserwacji zachowują stan znany w historycznym origin. Późna sprzedaż lub
korekta nie zmienia wcześniejszych lagów, labels treningowych ani predykcji.

[Końcowy odbiór](evidence/ai/02/data05/README.md) obejmuje powtórzenia obu smoke,
zgodne bajty demo i zachowanie IDs archiwów 2.0–2.5.
`source_ready=true` dotyczy obserwowanej sprzedaży. Modele, inventory i pełny
replay cross-repo mają własne dalsze bramki.

Pierwszy zakres 03 to typed Parquet, polityka artefaktów i niezmienny eksport
w RetailOps, następnie importer i curated w AI. Etap 11 jest odebrany;
równolegle można przygotować interfejsy i test doubles etapu 12. [Pisemna mapa](plans/ai/kolejnosc-i-repozytoria.md)
przypisuje etapy 03–17 do repozytoriów i podaje kolejność oraz możliwości
pracy równoległej. [Backlog](plans/ai/backlog.md) opisuje najbliższe zadania,
a [otwarte ustalenia](audits/open-findings.md) potwierdzone problemy.
Dowód zdalnego Required CI i publikacji na main: [audyt](evidence/ai/02/audit/README.md).

## Etap AI 11 — odebrany RAG

[Odbiór Etapu 11](evidence/ai/11/README.md) dotyczy `retailops-ai-intelligence`.
Zatwierdzony korpus ma 29 dokumentów i 451 fragmentów; rzeczywisty provider
Amazon Titan Text Embeddings V2 tworzy wektory 1024-wymiarowe z kontekstem nagłówków.
Na niezmienionych 44 pytaniach i progach: **Recall@5 85,3%, MRR 66,1%,
krytyczne 9/9, cytaty 100%**. Właściwy run ma `succeeded`, lokalny indeks
jest kwalifikowany i aktywny; SQL odtworzył wszystkie 44 wyniki.

Działają filtrowanie uprawnień/statusów, ograniczony context, trwałe runy,
retencja raportu przy niezaliczonym progu, kwalifikacja, atomowa aktywacja
oraz rollback. Lokalna regresja: 643 testy i pełny Compose z migracją
`0008_rag_semantic`, testami negatywnymi SQL, awariami i restartami.
Nie pozostały otwarte warunki Etapu 11. Agent, groundedness odpowiedzi
oraz wykonanie narzędzi należą do AI 12; pełny agent wymaga również AI 10.
Nie jest to wdrożenie AWS/EKS. Zmiana dokumentacji nie aktualizuje samoczynnie
zatwierdzonego indeksu — wymaga nowego snapshotu i oceny.
