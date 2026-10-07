AI09 follow-up: source2.8+knownplans jest przygotowany z osobnymi wariantami
schematów, pełnym process replay oraz testami native; nie jest odbiorem etapu.
[Evidence](evidence/ai/09/planned-anomaly-preparation.md) zachowuje też pojedynczy
Kafka coordinator read failure exact maincbcac6eb/CI37629010997 i ograniczoną
poprawkę helpera. PR #103 na `16d34887` zaliczył pełny Required CI
[37637743439](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/actions/runs/37637743439):
19 success, 4 celowe skipped, z zielonym required-result. Integracja nowszego
main `467f9903` zachowuje wspólny helper Kafka i wszystkie przyrosty AI 10.
18 testów offsetów, configured Ruff/format oraz mypy 43 źródeł są zaliczone;
pełne CI nowego head i chronionego main pozostaje wymagane.

# Aktualny status RetailOps

**2026-10-07: AI 09 pozostaje in_progress.**
[Odbiór komponentów producenta](evidence/ai/09/source-preparation/README.md)
opisuje ograniczenie kopii wejść oraz dziennego replayu inventory:
456 testów regresji i zgodne dane kontrolne. Pomiar pełnego profilu,
rzeczywista kampania i końcowa ocena pozostają wymagane. AI 07–08 są zamknięte.

**2026-10-07 — AI 10: READY, pełny odbiór integracji.**
[Raport i checklist](evidence/ai/10/README.md) wiążą snapshot/REST/stream,
Source SQL/capture → ten sam TLS/SCRAM broker → AI SQL/ACK oraz korektę 4 → 7.
Oryginalne publishery SQL dostarczyły 40 stockout, 1232 anomaly i 56 forecast;
Source sprawdził pełne projekcje, duplikaty, authenticated TCP API i built UI.
[Pełny V12](evidence/ai/10/v12-22de575.json), run `37665627162`, zaliczył
273 testy granic i rzeczywisty test Source bez failures/errors/skips.
Własne zasoby kontenerowe, sześć handoff objects i unikalny secret usunięto;
oryginalne S3 i inne sesje zachowano. [Source baseline CI](evidence/ai/10/source-code-main-ci.json)
ma 30/30; [nowszy scoped main CI](evidence/ai/10/source-b723489-main-ci.json)
21 success / 4 przewidziane skipped, a [AI main CI](evidence/ai/10/ai-b0-main-ci.json) 17/17.
Końcowe dokumenty podlegają normalnym protected merges i Required CI dokładnych main.
V12 pozostaje wyłącznie development z oryginalnym quality `not_ready`.
Sugestie są jawnym fixture AI10; rzeczywisty producent należy do AI12.
AI09 pozostaje odrębnym, otwartym etapem.

**AI 07 — READY na zaakceptowanych main, kwalifikacja `synthetic_ai_07_portfolio_v4`.**
Kompletny producent jest w [PR #97](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/pull/97),
a konsument w [PR #24](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/pull/24).
Oba PR-y są scalone. AI `18e771f9c2e89e91bf7afeb1744e0cd9112f50b5` i Source
`1de462729012a1bad458a8da4ad317ec22dbc5b8` mają odpowiednio zielony
[Required CI 37304852763](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/actions/runs/37304852763)
i [Required CI 37305855911](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/actions/runs/37305855911).
[Końcowy odbiór konsumenta](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/blob/main/docs/evidence/07-completion.md)
wiąże dwa rzeczywiste modele, 56/56 bramek, lifecycle, batch/API i restart OCI.
Frozen qualification source pozostaje `48439ebd9515dc1c7adc633609bbe33d1657c3df`;
scalenie z main zachowuje AI 05, prospektywny profil AI 08 i historyczne dane.
Niższe wpisy AI 07 dokumentują wcześniejsze zakresy odbioru.

**2026-10-05: AI 08 jest READY.** [Końcowy odbiór](evidence/ai/08/final/README.md)
i [receipt obu repo](evidence/ai/08/final/main-publication.json) potwierdzają
9296 punktów, 90 passed / 3 accepted warnings / 0 blockers, kwalifikowany model,
rzeczywisty MLflow/lifecycle/batch/API i zielone Required CI obu przyjętych main.
Wymagane prace AI 08: **0**. Odbiór był izolowany, bez wdrożenia produkcyjnego.

**AI 05 jest `ready`: [końcowy odbiór i publikacja](evidence/ai/05/final/README.md)**
obejmują rzeczywisty przepływ v12, oba scalone PR-y i zielony Required CI
na `main` obu repozytoriów. AI 04 jest zamknięty na v12 z trzema przyjętymi
odstępstwami MSE, a AI 06 ma odbiór danych inventory. Wejścia i lineage AI 08
są przyjęte w końcowym odbiorze; AI 07 pozostaje osobnym etapem.

Aktualizacja: **2026-10-02**. [Audyt AI 00](evidence/ai/00/README.md) na
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
| Dane i zdarzenia | Deterministyczny generator, walidacja kontraktów, Redpanda, konsument zdarzeń z atomową projekcją metryk, trwałą raw kwarantanną i [odtwarzaniem przed ACK](runbooks/realtime-recovery.md). Pełna ścieżka generator → broker → konsument wymaga osobnej weryfikacji. |
| CI i ochrona repozytorium | Required CI wybiera pełne kontrole obszarów, egzekwuje SHA Actions/digesty zewnętrznych obrazów i agreguje wynik `required-result`. [Aktualizacja wejść](runbooks/build-input-updates.md) odbywa się przez PR. Polityka `main` i jej ostatni zapis znajdują się w [governance](governance/branch-protection.md). |
| Wydania | Udokumentowane `v0.2.1`: obrazy Linux AMD64 w GHCR, podpisane provenance i SBOM, pobranie po digest oraz zgodny schematowo rollback. |
| Baza i rollback | Izolowane próby backup/restore oraz zmiany i przywrócenia wersji aplikacji; brak dowodu odwracalności dowolnych migracji schematu. |
| Kubernetes | Lokalny kind na ARM64/AMD64: ingress, NetworkPolicy, jobs, PVC, testy przeglądarkowe, restart i rollback. Ścieżka używa lokalnie budowanych obrazów. |
| Terraform | Kod fundamentu AWS, kontrolowany plan/drift i przygotowany backend S3/KMS. Ostatni spis z 2026-09-26 nie znalazł pasującego wdrożenia ani bucketu state; rola OIDC do planu była obecna. |
| Monitoring | Metryki API/DB/stream, Prometheus, Grafana i próba rzeczywistego firing/resolution alertu. SLO dotyczy scrape metryk; brak dowodu dostępności żądań użytkownika przez 30 dni i dostarczania powiadomień. |
| Jenkins | Rzeczywiste lokalne wykonanie pipeline z 2026-09-26; dodatkowa walidacja, bez wdrażania do chmury. |
| ML | Lokalna generacja cech, ocena RF z trzema oknami walidacyjnymi i odłożonym testem całego horyzontu oraz zweryfikowana ścieżka artefaktu do batchu, metadanych i metryk. [Ocena z 27.09.2026](evidence/ml/fixed-origin-rf-2026-09-27/README.md) odrzuciła RF wobec średniej ruchomej; brak kwalifikacji do serving. |
| Rozbudowa AI | [Fundament AI 01](evidence/ai/01/README.md) w osobnym repo: pakiet/CLI, HTTP/telemetry, PostgreSQL/pgvector, oddzielny MLflow i jawne migracje. Kontrakty danych/run/tool, walidacja offline i lokalne uprawnienia API: 267 testów na czystym checkoutcie oraz rzeczywisty HTTP z wheel poza źródłami. Principal pochodzi z prywatnych poświadczeń, cały scope jest egzekwowany; admin nie dziedziczy odczytów. Osobny wcześniejszy pomiar Compose: crash, trwałość, awaria DB i recovery. Etap 01 ma odbiór lokalny i zdalny: Required CI PR oraz push na main obu repo przechodzi, w tym persistence na Linux AMD64; dodatkowe testy bramki CI zwiększają zestaw do 273 testów. Zmiana grants/revoked wymaga restartu API; nie ma OIDC/production IAM lub serving. Źródło 2.6 ma lokalny i zdalny odbiór AI 02; snapshot/importer/curated AI 03 mają [odbiór cross-repo](evidence/ai/03/03.6/README.md) oraz publikację na main obu repo. |

## Zakres użycia

Projekt służy do lokalnego demo i weryfikacji praktyk DevOps. Przełączanie
`user_id` nie jest uwierzytelnianiem. Lokalny Compose przypina publikowane
porty do loopback zgodnie z [instrukcją](guides/local-development.md).

Działa lokalny MLflow w repo AI. Nie ma potwierdzonego produkcyjnego wdrożenia
AWS/EKS ani produkcyjnego model serving lub agenta Bedrock. Lokalny RAG ma
[odbiór AI 11](evidence/ai/11/README.md). Dalsze wdrożenia
opisuje [plan AI](plans/ai/README.md).

## Punkt wznowienia

[AI 08 — ryzyko stockout](plans/ai/etapy/08-stockout-risk.md) jest zamknięty.
AI 07 ma końcowy odbiór, publikację #97/#24 i zielone CI obu przyjętych mainów
wskazane powyżej. Jest ready. AI 10 jest w końcowym odbiorze opisanym na początku
tego dokumentu; AI 09 zachowuje własny zakres i zależności.
Nie otwieraj ponownie AI 08 na podstawie historycznych wpisów.
Poniższe wcześniejsze odbiory zachowują swoje wersje danych i zakresy.

[AI 03 — snapshot, importer i curated](plans/ai/etapy/03-snapshot-curated.md).
Źródło 2.6 przechodzi 46 hard gates; cechy AI 3.1 powstają w izolowanym workerze
z czterech projekcji faktów. Fingerprint obejmuje cały wykonywany kod, a wersje
obserwacji zachowują stan znany w historycznym origin. Późna sprzedaż lub
korekta nie zmienia wcześniejszych lagów, labels treningowych ani predykcji.

[Końcowy odbiór](evidence/ai/02/data05/README.md) obejmuje powtórzenia obu smoke,
zgodne bajty demo i zachowanie IDs archiwów 2.0–2.5.
`source_ready=true` dotyczy obserwowanej sprzedaży. Modele, inventory i pełny
replay cross-repo mają własne dalsze bramki.

[AI 03 — snapshot, importer i curated](evidence/ai/03/03.6/README.md) ma
pełny odbiór lokalny i Linux CI. Dwa standardowe smoke dwukrotnie oraz osobny
przypadek późnej korekty zachowują IDs, 25 tabel, typed CSV/Parquet parity
i historyczny as-of. Source przechodzi 46 hard gates; repo AI ma 747 testów.
Wszystkie przebiegi mieszczą się w 300 s / 1024 MiB.

**AI 06 ma [końcowy audyt i odbiór](evidence/ai/06/final/README.md).**
Domyślne CLI AI publikuje source 2.7 i snapshot 1.1; importer i curated 1.1
zachowują 43 facts/plans, native grain, causal availability i historyczny as-of.
Pełny pipeline obu profili dwukrotnie spełnia budżet 300 s / 1024 MiB.
Źródło/warstwa inventory są gotowe, modele wymagają własnego odbioru.
Frozen manifest źródła nadal ma pierwotne flagi false; readiness kolejnych
warstw zapisują curated i końcowy receipt. [Nowa karta danych](evidence/ai/06/final/dataset-card.md)
wiąże source/qualification/snapshot/curated IDs. Demo/API zachowują zgodność.
AI 04/05 mają [odbiór finalnego v12 i świeżego przepływu](evidence/ai/05/final/README.md).
Nowe wejścia 07/08 nadal wymagają własnych identyfikatorów, kwalifikacji i lineage.

AI 04/05 są odebrane na main obu repozytoriów; nowe wejścia 07/08 wymagają
własnej kwalifikacji i lineage.

**AI 07 ma kandydatów scenariuszy, handoff 2.8/1.2 i pełnego offline DQ.**
[Scenariusze](reference/business-anomaly-scenarios.md) zmieniają proces przed
finalnymi faktami i oddzielają prywatną truth od wejść operacyjnych.
[Pełny replay v2](reference/full-raw-dq-replay.md) obejmuje wszystkie sprzedaże
i native zgłoszenia zwrotów, również ogon po historii sprzedaży. Rozlicza błędy,
oryginalne lokalizacje, refundowane / odrzucone sztuki i brakujące fakty źródłowe.
[Odbiór 07.5](evidence/ai/07/07.5-full-dq/README.md) potwierdza oba przypadki
dwukrotnie w budżecie. Pełne pokrycie faktów nie oznacza kompletności dnia;
brakujące obserwacje pozostają nieznane. Odbiór nowego strumienia w AI,
kwalifikacja dni, baseline / IF, ewaluacja i anomaly lifecycle pozostają otwarte.
Cały AI 07 nie jest jeszcze ready.

[Karta danych](evidence/ai/03/03.6/dataset-card.md) podaje IDs i ograniczenia;
[runbook](reference/ai03-cross-repo.md) pozwala odtworzyć bramkę.
AI 03 jest na `origin/main` obu repozytoriów po scaleniu PR #65 i #5.
[Zapis publikacji](evidence/ai/03/03.6/main-publication.json) wiąże commity merge
z Required CI dla push na main. RAG 11 jest odebrany; prace AI 12 mają osobny worktree.
[Pisemna mapa](plans/ai/kolejnosc-i-repozytoria.md) podaje kolejność i podział repo.
[Backlog](plans/ai/backlog.md) zawiera najbliższe zadania,
a [otwarte ustalenia](audits/open-findings.md) potwierdzone problemy.

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
