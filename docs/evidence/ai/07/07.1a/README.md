# AI 07.1a — przygotowanie scenariuszy popytu

Odbiór lokalny: **2026-09-30**. Runtime:
`23a6a601093e5b3df7e61afaa42a0c77edc0949f`; branch
`ai/07-business-anomalies`, baza `origin/main`:
`1bc051bd1fe48c7201d6c1544e4dfc8669ff5e27`.
[Verification](verification.json) wiąże kod, konfigurację, IDs, checksumy,
wyniki i ograniczenia. [Instrukcja użycia](../../../../reference/business-anomaly-scenarios.md)
opisuje kontrakt i działającą komendę.

Zakres: `one_day_spike`, `multi_day_spike`, `sustained_drop`, ich osobne
etykiety oraz clean/promotion/seasonality/insufficient-history controls.
Mnożnik zmienia proces przed stochastic rounding i koszykami. Transakcje
przechodzą przez chronologiczny wspólny zapas i zwroty AI 06; ledger i commerce
są uzgadniane. Kandydat nie udaje nowego source 2.7 ani snapshotu AI 03.

## Próby wykonania

Darwin ARM64, Python 3.11.15, seed 42, `ai-smoke`, 30 dni,
8 produktów, 3 pary selling location/channel i 2 stock locations.
Historia: 2026-07-02–2026-07-31. Dwa świeże katalogi oraz jawny wariant
bez ograniczenia zapasu dały następujące wyniki:

| Przebieg | Czas [s] | Peak RSS [MiB] | Wynik |
|---|---:|---:|---|
| Domyślny zapas — pierwszy | 15.61 | 167.56 | passed |
| Domyślny zapas — powtórzenie | 10.71 | 203.02 | passed |
| Opening 10000 — kontrola obserwowalności | 14.40 | 227.47 | passed |

Pomiary obejmują generację, walidację i atomowy zapis z pełnym ponownym
wykonaniem obu procesów przed publikacją kandydata. To pomiary małej próby,
bez odbioru performance pełnych profili, cross-repo lub modeli.

Dwa podstawowe przebiegi mają identyczne ID
`anomaly-candidate-sha256-b436788169b5a6d1f9c46d74e25f4c8d488969f95ddbfe97cbacd78006958749`
oraz bajty wszystkich pięciu plików, łącznie z manifestem. Code provenance
jest `clean`. Trzy epizody i cztery okna kontrolne zostały rozliczone.

Domyślny inventory config ma opening 12. Jednodniowy skok zwiększa wtedy
popyt 24 → 72, ale observed pozostaje 0, a lost units wynoszą odpowiednio
24 i 72. Ten przypadek nie jest dowodem skoku obserwowanej sprzedaży.
Osobna jawna konfiguracja z opening 10000 zachowuje pozostałe parametry
i dowodzi rzeczywistego działania wszystkich trzech scenariuszy na sales:

| Typ | Okno UTC | Observed bez injekcji → z injekcją | Lost units |
|---|---|---:|---:|
| Jednodniowy skok | 2026-07-10 | 24 → 72 | 0 |
| Wielodniowy skok | 2026-07-17–2026-07-19 | 103 → 205 | 0 |
| Trwały spadek | 2026-07-24–2026-07-27 | 102 → 20 | 0 |

Duży opening jest syntetyczną kontrolą procesu, nie rekomendacją polityki
zapasów ani reprezentatywnym scenariuszem biznesowym.

## Weryfikacja

- **43 testy AI 07.1a passed** na zapisanym runtime: realne zmiany procesu,
  brak wycieku truth do facts/feature allowlist, granice dat i lifecycle,
  faktyczne czynniki kontroli, odrzucanie overlap, repeat/permutation,
  wersje i checksums, immutable publication oraz ponownie zapieczętowana
  podmiana etykiet odrzucana przez pełne odtworzenie procesu.
- **1042 testy regresji passed**: dotychczasowy generator, demand, dimensions,
  pricing/returns, identity, observation history, source/inventory,
  snapshot/Parquet i kontrakt zdarzeń. Pierwszy run miał 1039 passed i trzy
  błędy dostępu do socketa Docker w sandboxie. Wszystkie trzy przeszły po
  ponowieniu poza sandboxem z rzeczywistym izolowanym workerem. Zero skips
  i zero nierozwiązanych failures; łącznie **1085 różnych testów**.
- Ruff check i format zmienionego kodu: passed. Mypy nowego modułu
  `data/anomalies`, z `--follow-imports=skip`: 6 plików, passed; nie deklaruje
  to pełnego mypy historycznego generatora.
- 73 istniejące śledzone pliki demo, fixture i kontraktów zachowują blob IDs
  względem bazy. Kampania AI 04 i jej worktree/dane nie były modyfikowane.

Polecenia regresji i surowe XML są w ignorowanym `ci-cd/reports/data/`;
verification zachowuje ich checksums i rozliczenie ponowionych przypadków.
Nowe testy należą do istniejącej bramki `pytest data/tests` w Data CI.
Zdalny Required CI nie był uruchamiany; branch nie został opublikowany.

## Pozostały zakres i zależności

Return spike i jawnie wstrzyknięty inventory-censored episode, raw DQ faults,
nowa wersja source/snapshot oraz offline curation pozostają dalszą pracą.
Przed wspólnym handoff trzeba uzgodnić source zmieniane przez aktywne AI 04
i zachować zamrożone dane jego kampanii. AI-intelligence odpowiada za
PIT-safe expected/residual, baseline/IF, ewaluację oraz lifecycle po zgodnym
odbiorze AI 04/05.

Wszystkie kandydaty mają `source_ready=false`, `anomaly_ready=false` i
`model_ready=false`. Generatorowy counterfactual nie jest forecast expected
dla detektora. Cały AI 07 pozostaje otwarty. Produkcyjne projekcje, side effects
i transportowe ACK/DLQ wyników należą do AI 10.
