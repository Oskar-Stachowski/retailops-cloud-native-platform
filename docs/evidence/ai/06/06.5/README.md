# AI 06.5 — snapshoty ledgeru i stockout truth

**Odbiór lokalny 29.09.2026 na branchu `ai/06-01-inventory-ledger`,
implementacja `daa906a`.** Środowisko: macOS ARM64, Python 3.11.15
z `services/api/.venv`. [Rejestr](verification.json) zapisuje pełne SHA,
checksums, konfigurację, parent execution, komendy i wyniki.
[Kontrakt i uruchomienie](../../../../reference/inventory-projections.md)
opisują aktualne zachowanie. Następny zakres: **06.6 — integracja i publikacja danych**.

## Działające projekcje

Proces `inventory-projection-1.0.0` tworzy jeden operacyjny snapshot na fizyczny
produkt/warehouse/dobę UTC z ruchów dostępnych w jego cutoff. Ostatnia mikrosekunda
doby wyklucza receipt o kolejnej północy. Częściowe doby są jawne. Nieznane opening
daje null, a nie zero; późny receipt nie zmienia odtworzonego wcześniejszego as-of.
MVP ma `reserved_qty=0`, bez state machine rezerwacji i podwójnego wydania.

Osobna simulation truth uzgadnia fizyczne salda dobowe, jednorazowe opening,
epizody zero po każdym ruchu i lost-sales impacts. Granice epizodu zawierają czas,
sequence i źródłowy event. Chwilowe zero ma duration 0 i zachowuje utracony arrival.
Zero w opening jest left-censored; epizod bez recovery przed wyłącznym końcem
obserwacji jest right-censored z `end_at=null`. Brak sprzedaży przy dodatnim stanie
nie tworzy epizodu. Każdy dodatni lost-sales outcome jest przypisany dokładnie raz,
z fizycznym grainem i dotkniętym selling location/channel.

Prywatna diagnostyka siedmiodniowych okien rozróżnia już istniejący stockout,
nieznany/niedostępny stan w origin, niepełny tail i niedojrzałe outcomes.
Prawy koniec `(t,t+7 dni]` jest włączony, a obserwacja `end_at` wyłączona.
Przed pełną obserwacją i maturity nie powstaje ani 0, ani 1.
Wymagany truth delay oraz availability ruchów wyznaczają `label_available_at`.
To diagnostyka, bez publikacji label set ani odbioru modelu 08.

Normal fixture obejmuje dziewięć pełnych dób, jeden produkt i dwa warehouses:
**18 snapshotów**, 18 fizycznych sald, **3 epizody**, 1 impact i **4 utracone sztuki**.
Fizyczny końcowy stan 24/6 pozostaje zgodny z ledgerem 06.4.
Poor supply ma 5 epizodów, 4 impacts i 19 utraconych sztuk.
No-demand/zero-floor zachowuje dodatni warehouse bez epizodu i zerowy warehouse
z jednym otwartym epizodem bez utraconej sprzedaży.

## Weryfikacja

- **545 testów `data/tests`, zero błędów i pominięć**, w tym 60 nowych.
  Pełna regresja obejmuje wcześniejsze inventory, reorder, source, Parquet,
  snapshot/export/handoff i istniejącą bramkę cross-repo.
- Testy sprawdzają każdy dzienny grain, opening bez resetu, physical versus known,
  midnight cutoff, partial days, późne/przyszłe ruchy, instantaneous zero,
  no demand, zero-at-origin, siedmiodniowe granice i maturity.
  Celowo uszkodzone salda, lineage, epizody, duration, censoring, impacts,
  brakujące origins i fałszywe 0/1 nie przechodzą reconciliation.
- **16 rzeczywistych przypadków CLI na commicie implementacji**, poprzedzonych
  dziewięcioma wykonaniami generatora 06.4: normal/repeat, poor supply,
  no demand, zero stock, tail, instantaneous zero, future demand,
  immature outcomes, both classes, unknown opening oraz pięć błędnych wejść.
  Statusy `passed`/`not_ready`/`failed` i exit 0/1 są zgodne z oczekiwaniem.
  Oba hashes powtórnego wyniku są identyczne.
- Normal fixture ma jedną dojrzałą klasę i `not_evaluable` diagnostyki.
  Rozszerzenie obserwacji do 20 lipca i arrival 100 sztuk 7 lipca daje
  **14 okien klasy 0 i 5 klasy 1**. Diagnostyka jest evaluable,
  a `model_ready=false` nadal obowiązuje.
- Ruff check/format i mypy `--follow-imports=silent` przechodzą dla 23 plików
  inventory; test jest sformatowany. Dwa nowe JSON Schemas odpowiadają
  ścisłym modelom runtime.
- Oba dotychczasowe smoke wykonano po dwa razy: zachowane source IDs,
  po 46 hard gates i identyczne bajty CSV. Domyślny generator zachowuje fingerprint
  względem `68fe5d9`; świeże demo zachowuje 17 CSV, a 19 śledzonych plików
  jest zgodne z baseline.
- Pomiar projekcji małego fixture CLI: **0.0366 s / peak RSS 42.39 MiB**.
  Nie jest to benchmark standardowego smoke/dev/training chronologicznego źródła.

## Granice odbioru

Domyślny source 2.6 i opublikowane snapshoty 03 nie korzystają jeszcze z nowej
ścieżki. Integracja panelu, cen, koszyków, lifecycle/coverage, source gates
i nowa publikacja source/snapshot/curated należą do 06.6.
`inventory_ready=false`, DATA-06 i pełny odbiór źródła pozostają otwarte.
Nie ma nowych dataset IDs ani przepisanych metryk modeli.

Pełny raport projekcji zawiera private truth, nie jest eksportem API/cech.
Aktywny asortyment, poprawne forecast features, split, trening, kalibracja,
serving i odbiór stockout 08 nadal wymagają odrębnej realizacji.
Obie klasy diagnostyczne nie oznaczają gotowego modelu.

Kod, schematy, fixture konfiguracji i testy są w commicie implementacji;
osobny commit dokumentacji zawiera odbiór i aktualny plan. Pełne raporty
CLI/JUnit/compatibility pozostają pod ignorowanym `ci-cd/reports/data/`,
a rejestr w Git zachowuje checksums i wyniki. Nie wykonano zdalnego Required CI
ani publikacji AI 06 na main.
