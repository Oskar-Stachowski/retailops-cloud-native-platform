# AI 02 / DATA-02/03/05 — popyt, panel i koszyki

Odbiór lokalny **2026-09-28**, branch ai/02-demand-panel, kod
`7dad24f3e36419d965cb084fa0e09b7734012197`, baza DATA-04
`138e48477f7965de907098ccb169774b5451d049`.
Zakres: punkt 4 instrukcji etapu 02, bez końcowego odbioru całego etapu.
Nowszy [odbiór DATA-03](../data03/README.md) potwierdza chronologię i zwroty
źródła 2.4. Bieżący pełny odbiór source 2.6 i workera: [DATA-05](../data05/README.md).
Punkt wznowienia: [AI 03](../../../../plans/ai/etapy/03-snapshot-curated.md).

## Kontrakty i zachowanie

[Specyfikacja](../../../../reference/daily-demand.md) opisuje jedną formułę
popytu z demand weight dokładnie raz. Ilości każdego ważnego dnia/podmiotu
powstają przed koszykami; stochastic rounding pozwala na prawdziwe zero.
Deterministyczne koszyki dobierają komplementarne SKU bez replacement oraz
zachowują cały dzienny budżet. Order/items/sales, sztuki i przychód się uzgadniają.

| Kontrakt | Wariant tego pomiaru |
|---|---|
| Generator / source schema | 0.5.0 / 2.3.0; 34 CSV AI i 17 legacy. |
| Daily demand | daily-demand-1.0.0; observations, inactive exclusions i oddzielna simulation truth. |
| Grain | business_date/product_id/selling_location_id/channel; fizyczna lokalizacja. |
| Kompletność | Wszystkie i tylko ważne kombinacje; observed positive/zero, closed i missing; inactive poza mianownikiem. Missing jest null, blokuje kompletny eksport. |
| Availability | Zamknięcie doby o następnej północy UTC lub późniejsza ingestia/wycena faktów. Watermark panelu jest jawny; dane po nim blokują kompletność. |
| Cechy | AI 3.0: pełny grain/statusy, bez inventory, revenue/realized price i truth. Calendar lag używa dokładnej daty i known-at; luka/closed/late są unknown. Legacy 2.0 pozostaje dla demo i obecnego RF. |
| Identity | Canonicalization 1.3.0 i demand policy; parent feature obejmuje pełny source. Seed/rozmiar zmieniają oba ID. |
| Zwroty | Net revenue/return units puste, return_data_complete=false; istniejące zwroty nie są zatwierdzonym źródłem net ani zerem. |
| Odczyt historyczny | Rzeczywiste source 2.0/2.1/2.2 i feature 2.0 odczytane z niezmienionymi IDs/parent. |

Parametry klas i mnożniki są syntetyczną wersjonowaną polityką, bez deklaracji
kalibracji rynku. Nie ma wiarygodnego inventory cap, ledgeru ani lost-sales.
Daily truth nie trafia do sales ani macierzy cech. Parametry products/stores
oraz granice dostępu procesu/runtime wymagają jeszcze dalszego rozdzielenia.

## Wykonane próby

[acceptance.json](acceptance.json) pochodzi z czystego wskazanego commita:
dwa ai-smoke i dwa ai-temporal-smoke, kontrasty seed 42/43 i 8/9 produktów.
Powtórzenia mają identyczne source/feature IDs, bajty CSV, raporty wymiarów i
demand. Sześć nowych hard gates, osiem wymiarów, sześć pricing oraz dotychczasowe
15 kontroli strukturalnych przechodzi. Koszyki nie mają powtórzonego SKU.

| Profil | Nominalna siatka | Pełny ważny panel / cechy | Dodatnie | Jawne zero | Closed | Inactive poza panelem |
|---|---:|---:|---:|---:|---:|---:|
| ai-smoke | 1 800 | 1 612 | 1 292 | 177 | 143 | 188 |
| ai-temporal-smoke | 2 448 | 2 406 | 1 865 | 281 | 260 | 42 |

Coverage ważnego panelu wynosi **100%** w obu profilach. W ai-smoke jest 6096
linii sprzedaży, w temporal 10817; agregacja nie gubi ani nie dodaje sztuk.
17 CSV demo i ograniczonego small są zgodne bajtowo z bazą DATA-01;
19 śledzonych plików demo nie zmieniono. Dane powstają w temp.
Sekwencyjny odbiór trwał **46,91 s** przy peak RSS **112,31 MiB** na macOS:
generacja źródeł/cech i walidacja, bez treningu lub pełnego ai-training benchmarku.

[verification.json](verification.json) zapisuje **585 testów**, 0 failures/errors/skips,
w tym PostgreSQL i API; coverage API **83,82%**, próg 70%.
42 testy tego zakresu obejmują zera/closed/inactive/missing, pojedynczą wagę,
konserwację budżetu dla wielu seedów, losowanie komplementów, zgodność agregatów,
calendar lag, cutoff mikrosekundowy, semantic validation cech, watermark,
archiwum 2.2 i zgodność kontraktów. Brak dnia, powtórzony SKU, podwojona waga,
fałszywe sumy/statusy/dostępność albo dodane pole truth są odrzucane.
Przeliczenie hashów źródła z usuniętym dniem nie omija bramki panelu.

Ruff, format, skonfigurowane mypy (5 modułów API), Bandit high/high i Gitleaks
przechodzą. Cztery poprawne polecenia source/feature CLI kończą się 0;
niepełny CSV panelu i uszkodzony CSV cech kończą się 1. Testy DB używają
świeżych migracji i seeda demo na izolowanym PostgreSQL 16; kontener został usunięty.
Zdalnego Required CI ani nowej oceny modelu nie wykonywano.

## Odtworzenie i ograniczenia

Z repo z przygotowanym środowiskiem API na wskazanej rewizji:

```bash
services/api/.venv/bin/python -m scripts.data.verify_demand_panel \
  --output /tmp/retailops-demand-acceptance.json \
  --baseline docs/evidence/ai/02/data01/legacy-baseline.json --require-clean
PYTHONPATH=.:services/api services/api/.venv/bin/python -m pytest \
  services/api/tests/test_data_demand.py -q
```

Pełne polecenie pytest i zakres DB znajdują się w verification.json.
Źródło i cechy zachowują not_ready dla forecastingu, anomaly, stockout i replay,
inventory_ready=false. Pełny panel nie certyfikuje poprawności zwrotów,
izolacji truth, historii korekt, modelu ani transportu. Chronologię/zwroty
i izolację procesu kwalifikuje bieżący [odbiór source 2.6](../data05/README.md).
Historia korekt i importer pozostają etapem 03.
