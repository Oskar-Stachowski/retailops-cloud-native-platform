# AI 07.1b — zwroty i fizyczne ograniczenie zapasu

Odbiór lokalny: **2026-10-02**. Runtime:
`ffbf9e9dce4081cb4097df48c595e8a0920853a9`; branch
`ai/07-business-anomalies`, baza `origin/main`:
`6ccbe3de0aefc97cc221a279d5fe83aa338b3601`.
[Verification](verification.json) wiąże kod, konfigurację, ID, checksums,
próby, testy i ograniczenia. [Instrukcja użycia](../../../../reference/business-anomaly-scenarios.md)
opisuje wersjonowany kontrakt i CLI.

Zakres: `return_spike` oraz `inventory_censored_episode`, każdy z poprzedzającym
clean control. Uzupełnia [07.1a](../07.1a/README.md), więc lokalny producent
obsługuje pięć wymaganych typów business scenarios. Oba nowe epizody zmieniają
rzeczywisty proces źródłowy. Nie są nowym source/snapshotem ani odbiorem modeli.

## Próby wykonania

Darwin ARM64, Python 3.11.15, seed 42, `ai-smoke`, 30 dni,
8 produktów, 3 pary selling location/channel i 2 stock locations.
Historia: 2026-07-02–2026-07-31. Domyślny opening wynosi 12.
Dwa świeże katalogi po zapisaniu czystej rewizji kodu:

| Przebieg | Czas [s] | Peak RSS [MiB] | Wynik |
|---|---:|---:|---|
| Fizyczne scenariusze — pierwszy | 13.29 | 157.91 | passed |
| Fizyczne scenariusze — powtórzenie | 10.91 | 183.19 | passed |
| Poprzedni CLI popytu v1 — kontrola zgodności | 9.31 | 197.67 | passed |

Czas obejmuje generację, walidację, pełne niezależne powtórzenie pary
procesów i atomową publikację lokalnego kandydata. Nie odbiera performance
pełnych profili treningowych ani ścieżki cross-repo nowych scenariuszy.

Oba fizyczne przebiegi mają ID
`anomaly-candidate-sha256-5fcec0281468fcda78ca0126b1cc91a5cd7fc042b1c53857b1c5b1804d609ba3`
i identyczne bajty wszystkich pięciu plików, łącznie z manifestem.
Code provenance jest `clean`. Rozliczono dwa epizody i dwa clean controls.

| Epizod | Okno UTC | Bez injekcji → z injekcją |
|---|---|---|
| `return_spike` | 2026-07-14–2026-07-20 | Returned units 12 → 26; events 9 → 21; refunded units 11 → 24 |
| `inventory_censored_episode` | 2026-07-10 | Latent 17 → 17; observed 3 → 0; lost 14 → 17; fizyczny write-off 3 sztuk |

Zwroty dotyczą rzeczywiście zakupionych sztuk, zachowują policy windows,
chronologię, statusy i podział zakupu. Mnożnik 20 działa na wybór części
w grain daty zwrotu, z niezmienionym maksymalnym prawdopodobieństwem 0,75.
Zaakceptowane restocks zwiększyły observed w oknie zwrotów 64 → 69 przy tym
samym latent 208. Raport obejmuje wszystkie cztery grain ze zmienioną
sprzedażą, bez ukrywania wtórnego skutku zwrotów dla inventory.

Cap=0 usuwa rzeczywisty zapas przez ujemny `write_off` przed demand arrival,
także dla innych kanałów używających tej puli. Dostawy i zwroty pozostają
normalnymi procesami; cap stosuje się ponownie przy kolejnym arrival w oknie.
Nie jest to ciągły cap między arrival. Powiązanie write-off z injection ID
pozostaje w truth, poza operacyjnymi facts. Latent demand wszystkich arrival
w obu przebiegach jest identyczny. Łączna reconciliation:
`4796 = 2402 observed + 2394 lost`, 1390 sales, 101 receipts i 480 snapshots.

## Weryfikacja

- **190 różnych testów passed, zero skips i zero nierozwiązanych failures.**
  Obejmują 67 testów scenariuszy popytu/fizycznych, rzeczywistą realizację
  commerce/inventory, source writer/reader, zwroty oraz obie szybsze ścieżki.
  Negatywne przypadki odrzucają overlap/shared-product spillover, zły routing,
  seed/version, daty poza zakresem, nieskuteczną injekcję i ponownie
  zapieczętowaną podmianę etykiet. Powtórzenie i permutation są identyczne;
  prywatne parametry nie trafiają do facts.
- Pierwsza regresja miała 174 passed, jeden failure i 15 setup errors:
  zabezpieczenie szybszych ścieżek odrzuciło zmienione checksumy upstream.
  Po przeglądzie opcjonalnych gałęzi i potwierdzeniu niezmienionych zwrotów
  odświeżono przypięcia; wszystkie 16 przypadków przeszło ponownie.
  Potwierdzono dokładnie 58 tabel, CSV bytes i context normalnej/indexed/cached
  generacji, zwykłą publikację ze wszystkimi 36 source gates oraz nadal
  działające odrzucanie duplikatów, ujemnego stanu i driftu kodu.
- Domyślna generacja 461 return events na tej konfiguracji jest dokładnie
  identyczna z funkcją odczytaną z bieżącego `origin/main`. Osobny test
  potwierdza niezmienione events poza scope i brak nadmiernych zwrotów.
  Wszystkie 73 istniejące śledzone demo, fixtures i contracts mają te same
  bajty co baza; nowy fizyczny kontrakt jest osobnym plikiem.
- Ruff check/format zmienionego runtime: passed. Mypy `data/anomalies`,
  `--follow-imports=skip`: dziewięć plików, passed. Nie jest to pełny mypy
  historycznego generatora.

Komendy oraz checksumy XML są w verification; duże lokalne artefakty i surowe
raporty pozostają w ignorowanych `data/generated/` i `ci-cd/reports/data/`.
Zdalny Required CI zostanie zapisany osobno po publikacji brancha.
Worktree, dane, procesy, usługi serving i stan MLflow sesji AI 05 nie były
modyfikowane. Zmiany RetailOps są w osobnym worktree i nie zmieniają jej
bieżącego checkoutu.

## Pozostały zakres

Następny niezależny krok to **07.2: realne raw DQ faults z osobnym kontraktem
i truth**, następnie bounded offline replay/curation i wersjonowany handoff
AI 03. Uzgodnić generator/snapshot z AI 04; dotychczasowe frozen dane pozostają
bez zmian. PIT-safe expected/residual, baseline/IF, ewaluacja wielu seedów
i lifecycle w repo AI wymagają zgodnych odbiorów AI 04/05.

Każdy kandydat zachowuje `source_ready=false`, `anomaly_ready=false` i
`model_ready=false`. Próba zawiera po jednym pozytywnym epizodzie każdego
nowego typu; nie jest reprezentatywną ewaluacją detektora. Cały AI 07 pozostaje
otwarty. Produkcyjne projekcje, ACK/DLQ i integracja wyników należą do AI 10.
