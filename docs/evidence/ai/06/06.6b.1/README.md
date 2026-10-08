# AI 06.6b.1 — typowane tabele inventory

**Odbiór lokalny 29.09.2026, branch `ai/06-01-inventory-ledger`,
implementacja `5184ec9`, odbiór CLI `b52a422`.** [Rejestr](verification.json) przypina pełne SHA,
komendy, konfiguracje, checksums i wyniki. Środowisko: macOS ARM64,
Python 3.11.15, PyArrow 25.0.1, `services/api/.venv`.
[Kontrakt i uruchomienie](../../../../reference/inventory-source-tables.md)
opisują rozszerzenie `inventory-source-tables-1.0.0`.

## Zakres

27 ścisłych tabel materializuje wynik source-commerce oraz pełne projekcje
06.5: **19 operational facts/plans i 8 private simulation truth**.
Każda ma deklarowany grain, typy i nullability. CSV/Parquet zachowuje
ilości `int64`, flagi `bool`, kwoty decimal, daty oraz timestamp UTC
z mikrosekundami, także dla pustych tabel.

Odczyt sprawdza allowlistę, placement facts/truth, schemas, checksums,
logical hashes, ID i wszystkie wiersze obu formatów. Odtwarza ledger/supply
i ponownie uzgadnia sprzedaż, refund/disposition/restock, kompletność arrivals,
snapshoty, fizyczne salda, epizody, utracone sztuki i dojrzałość diagnostyki.
Sprawdza route revision lineage, scope polityki/history oraz pełne ilości
wykonanych i przyszłych receipts wobec zamówień. Nie uruchamia generatora
w celu uzgodnienia zapisanych tabel.

Kandydat powstaje w staging i jest przenoszony po weryfikacji.
Reuse odczytuje istniejące pliki, nie naprawia uszkodzonych danych.
ID `inventory-tables-candidate-sha256-*` wiąże kontrakt/context,
parent execution i kanoniczne tabele; nie zastępuje IDs ścieżki 03.
Cache dat i kluczy nie zmienia rekordów ledgeru. Sumy prefiksowe zachowują
ścisłe porównanie timestamp/sequence i historyczne granice availability.

## Odbiór profili

Oba standardowe profile wykonano **dwukrotnie na czystym runtime commita**,
od świeżej integracji koszyków do typowanych tabel i ponownego odczytu.
Parent execution, candidate ID, hashes faktów/truth oraz wszystkie table
descriptors, w tym bajty CSV/Parquet, są zgodne w powtórzeniach.

| Profil | Arrivals | Sold units | Lost units | Daily snapshots | Stockout episodes | Right-censored | Lost-sales impacts |
|---|---:|---:|---:|---:|---:|---:|---:|
| `ai-smoke`, 30 dni / 20 produktów / 3 stores / 2 stock locations | 6096 | 5580 | 5467 | 1200 | 189 | 9 | 2954 |
| `ai-temporal-smoke`, 102 dni / 8 produktów / 3 stores / 2 stock locations | 10817 | 11333 | 8608 | 1632 | 314 | 6 | 4566 |

Każdy snapshot i physical daily balance ma osobne uzgodnienie, a każde
dodatnie lost outcome dokładnie jeden impact. Kanały korzystają ze wspólnego
stock. Liczba window diagnostics odpowiada pełnemu dziennemu fizycznemu grainowi.
Immature tail nie otrzymuje wymyślonego 0/1.

**8 przypadków rzeczywistego odbioru CLI:** oba profile po dwa razy,
supply-poor, zero opening, późna availability (`not_ready`) oraz uszkodzony
parent (`failed`, bez artefaktów). Status i exit 0/1 są zgodne.
Każdy poprawny proces source-commerce plus native tables mieści się
w **300 s / 1024 MiB**; rzeczywiste pomiary obu subprocessów są w rejestrze.
Ten pomiar nie obejmuje nowego source quality, eksportera, importera ani curated.

## Weryfikacja i zgodność

- **642 testy `data/tests`, bez błędów i pominięć; 48 nowych.**
  Nowy zestaw obejmuje strict schema/grain, native types/nulls, powtórzenia,
  reuse, niezmienność wejść i real CLI.
- **28 uszkodzonych tabel/procesów** odrzucono przed zapisem: opening/issue,
  sale/location/demand, snapshots/physical balances, episodes/impacts/maturity,
  supplier/receipt/tail, return disposition, route, rule/history scope, typy
  i nielegalne tables/columns.
- **9 prób uszkodzenia odczytu** nie przechodzi: CSV/Parquet, dodatkowy plik,
  reclassification truth, readiness, ID, ścieżka, cutoff i symlink.
  Reuse nie nadpisuje uszkodzonego manifestu. Cztery zmienione parent receipts
  są odrzucane przez kontrolę hashes i execution ID.
- Kontrolowane no-demand i zero-opening fixtures zachowują typy pustych tabel.
  Zero opening może tworzyć epizod z zerowym lost sales; brak popytu przy
  dodatnim stock nie staje się stockout.
- Ruff check/format i mypy przechodzą dla **35 plików runtime/acceptance**.
  Checked-in JSON Schema odpowiada modelom wykonywanym przez czytnik.
- Domyślny source zachowuje fingerprint względem `68fe5d9`, oba dotychczasowe
  IDs, po 46 hard gates oraz bajty CSV w dwóch powtórzeniach obu profili.
  Świeże demo zachowuje **17 CSV**, a **19 śledzonych plików** zgadza się
  z baseline. Frozen fixtures/kontrakty 03 nie zostały nadpisane.

## Pozostałe warunki AI 06

Ten odbiór dotyczy **kandydata tabel**, bez nowego source/snapshot/curated.
`source_ready=false`, `inventory_ready=false`, `model_ready=false`;
inventory lifecycle/label qualification ma `not_evaluated`.
DATA-06 i pełny AI 06 pozostają otwarte.

Następny zakres **06.6b.2** włącza tabele do nowego domyślnego source:
wersji, identity, konfiguracji, manifestów i pełnych quality/realism/readiness
oraz kwalifikacji lifecycle/coverage. Potem należy odebrać nowy immutable
eksport/import/curated przez rozszerzoną ścieżkę 03, pełną bramkę cross-repo
i zależne reevaluation 04/05. Dotychczasowe metryki nie przechodzą na nowe IDs.
To nie odbiór modelu 08, nowych feature contracts ani model serving.

Repo AI i worktree AI 12 nie były modyfikowane. Implementacja i dokumentacja
mają osobne lokalne commity na branchu AI 06. Pełne raporty/artefakty/JUnit
pozostają pod ignorowanym `ci-cd/reports/data/`; Git zachowuje mały rejestr.
Nie wykonano nowego zdalnego Required CI ani publikacji AI 06 na main.
