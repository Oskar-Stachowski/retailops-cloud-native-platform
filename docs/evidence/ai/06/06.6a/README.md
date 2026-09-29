# AI 06.6a — chronologiczna realizacja koszyków źródłowych

**Odbiór lokalny 29.09.2026 na branchu `ai/06-01-inventory-ledger`,
implementacja `01c4170`.** Środowisko: macOS ARM64, Python 3.11.15
z `services/api/.venv`. [Rejestr](verification.json) wiąże pełne SHA,
konfiguracje, komendy, checksums i wyniki z commitem.
[Kontrakt i uruchomienie](../../../../reference/source-inventory-commerce.md)
opisują proces `source-inventory-commerce-1.0.0`.
Następny zakres: **06.6b — wersjonowany domyślny source i publikacja danych**.

## Wykonane połączenie

Osobna ścieżka traktuje dotychczasowe nieograniczone koszyki jako prywatny popyt
i realizuje je przez chronologiczny wspólny ledger. Opening jest jawny i występuje
raz na fizyczny product/location. Faktyczna sprzedaż ma dokładnie właściwe issue,
historyczny mapping i oryginalny koszyk/pozycję. Brak stock nie staje się sprzedażą
ani losową flagą; pełny panel zachowuje ważne grains, także z zerową sprzedażą.

Częściowa realizacja ponownie rozwiązuje cenę dla **kupionej ilości** w czasie
zamówienia. Zachowuje warunki quantity-based bundle, usuwa puste koszyki
i przelicza kwoty. Zwrot nie przekracza kupionej ilości; refund korzysta
z zapłaconej ceny. Finansowo odrzucony i jakościowo odrzucony to odrębne decyzje.
Uszkodzony produkt może mieć refund bez restocku. Przyjęcie i rozliczenie finansowe
mają osobne availability; zwroty poza oknem inventory nie rozszerzają historii
popytu ani nie tworzą przyszłego stock.

Panel, historyczne wersje observed quantity, price aggregates i return cohorts
powstają z faktycznych sprzedaży oraz causal availability. Późniejszy fakt
nie zmienia wcześniejszej kohorty; dodaje wersję obserwacji. Raw ingestion
pozostaje zapisane osobno. Inventory snapshots mają własny fizyczny grain
i cutoff ostatniej mikrosekundy doby; quantity, jednostka, lineage oraz
legacy projection są uzgadniane niezależnie z ledgerem.

## Standardowe profile

Oba profile wykonano **dwukrotnie na commicie implementacji**.
Execution ID, hashes operational/truth i hash wejściowych tabel są zgodne.

| Kandydat | Arrivals | Latent units | Sold units | Lost units | Sale issues | Inventory snapshots |
|---|---:|---:|---:|---:|---:|---:|
| `ai-smoke`, 30 dni / 20 produktów / 3 stores / 2 stock locations | 6096 | 11047 | 5580 | 5467 | 3228 | 1200 |
| `ai-temporal-smoke`, 102 dni / 8 produktów / 3 stores / 2 stock locations | 10817 | 19941 | 11333 | 8608 | 6374 | 1632 |

Smoke uzgadnia 260 receipts / movements, 571 finansowych return events
i 112 quality-accepted restocks. Temporal smoke uzgadnia 376 receipts / movements,
1033 finansowe return events i 304 accepted restocks. Na każdym ważnym dziennym
grainie `observed + lost = latent`; cena, refund i bilans zapasu mają właściwe FK.

Zmierzony kandydat smoke: **13,30–15,27 s**; temporal: **63,87–66,39 s**.
To czas osobnej ścieżki integracji. Nie jest to odbiór budżetu całego nowego
pipeline source → export → import → curated ani benchmark dev/training.
Peak RSS każdego rzeczywistego subprocess jest zapisany w rejestrze.

## Weryfikacja

- **594 testy `data/tests`, zero błędów i pominięć**, w tym 49 nowych.
  Regresja obejmuje wcześniejsze inventory, source, Parquet, exporter/handoff
  i dotychczasową bramkę cross-repo.
- Nowe testy sprawdzają konserwację popytu, shared physical stock, snapshoty,
  częściowe koszyki, utratę rabatu bundle poniżej minimum, eligibility refundu,
  quality rejection, oryginalny magazyn, financial tail oraz historyczne as-of.
  Zmiana supplier truth nie zmienia pierwszej decyzji reorder przed receipt.
- **25 celowo uszkodzonych wyników** nie przechodzi bramki: sprzedaż/pozycja/cena,
  ingestion, koszyk i totals, powtórzenia/brak FK, truth w facts, panel/history/cohort,
  zwrot i warehouse/disposition, lineage route, snapshot/legacy, loss/receipt
  oraz granica obserwacji.
- **11 rzeczywistych przypadków CLI:** dwa standardowe profile po dwa razy,
  supply-poor, zero opening, późna availability (`not_ready`) i cztery błędne
  konfiguracje (`failed`). Statusy i exit 0/1 są zgodne z oczekiwaniem.
- Ruff check/format oraz mypy `--follow-imports=silent` przechodzą dla 30 plików
  inventory. Nowy JSON Schema odpowiada ścisłemu modelowi runtime.
- Domyślny generator zachowuje fingerprint względem `68fe5d9`.
  Oba stare source profiles wykonano po dwa razy: te same IDs, bajty CSV
  i po 46 zaliczonych hard gates. Świeże demo zachowuje **17 CSV**;
  **19 śledzonych plików** jest zgodne z baseline.

## Granice odbioru i pozostała praca

Ten odbiór dotyczy **nieopublikowanego kandydata integracji**.
Jego ID `source-inventory-candidate-sha256-*` nie jest nowym source dataset ID,
snapshot ID ani curated ID. Raport zawiera private truth i nie jest wejściem
API, loadera seeda ani feature workera. Domyślny source 2.6, opublikowane dane 03
i wcześniejsze evidence pozostają niezmienione.

`source_ready=false`, `inventory_ready=false`, DATA-06 i pełny AI 06 pozostają
otwarte. 06.6b musi wersjonować domyślny source i jego typed inventory/supply tables,
manifesty/identity, pełne quality/realism/readiness, lifecycle/coverage i projekcje
06.5 oraz wykonać nowy immutable eksport/import/curated przez rozszerzoną ścieżkę03.
Pełna kwalifikacja źródła i bramka cross-repo poprzedzają deklarację inventory ready.

Zmiana censoringu wymaga zgodnego feature schema i ponowienia 04/05 przed
wykorzystaniem forecastu przez anomaly/stockout. Nie przeniesiono wcześniejszych
metryk modeli. Trening, split, kalibracja, serving i odbiór 08 są osobnym zakresem;
`model_ready=false`. Repo AI i worktree AI 12 nie były modyfikowane.

Kod, schema, fixture konfiguracji i testy są w commicie implementacji.
Osobny commit dokumentacji zawiera odbiór oraz aktualny plan.
Pełne raporty CLI/JUnit/compatibility są ignorowane pod `ci-cd/reports/data/`;
rejestr w Git zachowuje checksums i wyniki. Odbiór jest lokalny, bez publikacji
AI 06 na main ani nowego zdalnego Required CI.
