# Audyt AI 02 i gotowość do AI 03

**Decyzja: można przejść do realizacji AI 03**, zaczynając od typed Parquet
i polityki artefaktów w RetailOps. Źródło 2.6 jest zakwalifikowane do
snapshotu syntetycznej sprzedaży `observed_sales_units`; brak blokerów wejścia.

Audyt dotyczy implementacji `5a8678c` i regresji `152341e` na branchu
`ai/02-data-05`. [Wynik maszynowy](verification.json) zapisuje fingerprinty,
polecenia, wyniki, ograniczenia i stan publikacji. Pełny odbiór źródła:
[DATA-05](../data05/README.md). Warunki kolejnego etapu:
[AI 03](../../../../plans/ai/etapy/03-snapshot-curated.md).

## Obecne gwarancje

| Obszar | Dowód |
|---|---|
| Konfiguracja i identity | Jawne daty/parametry, powtarzalne source/feature IDs i bajty. Seed, rozmiar i data zmieniają IDs. Archiwa 2.0–2.5 zachowują tożsamość. |
| Wymiary, czas i ceny | Fizyczne lokalizacje/kanały, lifecycle i PL/DE-BE z DST; znane plany, scope, konflikty i wspólna wycena transakcji. |
| Panel, koszyki, zwroty | Pełna aktywna siatka, zero/closed/missing, konserwacja sztuk i przychodu, chronologia pozycji, refundacje oraz dojrzały ogon. |
| Separacja i runtime | 46 hard gates, osobne simulation truth i operational outputs; rzeczywisty worker przyjmuje tylko cztery projekcje faktów. |
| Provenance kodu | Fingerprint obejmuje wszystkie siedem plików wykonywanego bundla, łącznie z inicjalizatorami. Każda mutacja zmienia code hash/feature ID przy identycznych wierszach i ma modified provenance. |
| Historia obserwacji | Ciągłe append-only wersje z availability; odczyt ostatniej wersji znanej w origin. Późna sprzedaż i korekta nie zmieniają dawnych lagów, labels treningowych ani RF/baseline predictions. Brak historii daje missing_history. |

Regresje provenance: [test_worker_provenance.py](../../../../../services/api/tests/test_worker_provenance.py).
Granice czasu, wersje, korekty i wszystkie okna oceny:
[test_observation_history.py](../../../../../services/api/tests/test_observation_history.py).
Źródło i schema historii: [dzienny popyt](../../../../reference/daily-demand.md).

## Weryfikacja

Ponowny `scripts.data.verify_data05 --require-clean` przeszedł dziewięć
przebiegów: oba smoke dwukrotnie, kontrasty seed/rozmiar/daty oraz DST ze
wszystkimi kanałami. Każdy przebieg ma 46/46 hard gates. Zgodne są bajty,
raporty, source/feature IDs i watermarki. Zachowano 17 CSV demo/small,
19 śledzonych plików demo oraz IDs sześciu historycznych eksportów.

Dziesięć prób rzeczywistej izolacji Docker przeszło; podanie truth/inventory
bezpośrednio do workera jest odrzucane. Poprawne CLI zwracają 0, uszkodzone
bajty source/features — 1. Supervisor pozostaje zaufanym właścicielem source.
Worker nie ma sieci, repo, generatora, źródłowych plików ani socketu Dockera.

**670 testów bez failures/errors/skips, coverage API 83,82%** oraz Ruff/format
(152 pliki), mypy, Bandit high/high i Gitleaks
zapisano w [verification.json](verification.json). Testy DB używają świeżego
PostgreSQL 16 po migracjach i seedzie. Pomiary lokalne: macOS ARM64, worker
Linux ARM64 przez Docker Desktop. RSS workera nie był mierzony; limit to 256 MiB.
Nie wykonano benchmarku ai-dev/ai-training ani nowej oceny modelu.

## Publikacja i dalsza praca

Całość AI 02 opublikowano przez [PR #61](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/pull/61) na
main, merge `30e3e70`. Required CI dla
[PR](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/actions/runs/36444858612) i [push na main](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/actions/runs/36446776645) ma **success**,
łącznie z API, full-stack Compose, kind/persistence/rollback oraz kontrolami
security i danych na Linux AMD64. `required-result` jest zielony; ochrona
main pozostała aktywna. [verification.json](verification.json) zapisuje SHA,
job IDs i wyniki obu przebiegów. Pierwsza próba Kubernetes po rollbacku
przekroczyła 5 s oczekiwania dashboardu; API odpowiedziało 200 po 5,17 s.
Ponowienie wyłącznie nieudanej próby i zależnej bramki przeszło na świeżym
runnerze bez zmian kodu. Receipt zachowuje pierwszy wynik i identyfikator artefaktu.
Ten kolejny commit uzupełnia wyłącznie dokumentację.

AI 03 implementuje Parquet, immutable export, kontrakt cross-repo, importer
i curated. Musi zachować istniejące wersje i dostępność; nie deklarować
poprawności historycznej dla źródeł, które nie dostarczają potrzebnej historii.
AI 04 i 06 wymagają później dwukrotnego generator → export → import → curated
na obu smoke zgodnie z bramką końca AI 03.

Forecasting/model serving, anomaly, stockout i pełny replay cross-repo pozostają
not_ready; inventory_ready=false. DATA-06 należy do ledgeru AI 06, OPS-03/07
do integracji AI 10, OPS-06 do odbioru wydań. Te otwarte zakresy nie blokują
pierwszego plikowego snapshotu sprzedaży bez cech zapasu. Nie wymagamy brokera,
operacyjnej DB ani AWS do rozpoczęcia AI 03.
