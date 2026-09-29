# AI 06.4 — chronologiczny wspólny zapas i sprzedaż

**Odbiór lokalny 29.09.2026 na branchu `ai/06-01-inventory-ledger`,
implementacja `b776adf`.** Środowisko: macOS ARM64, Python 3.11.15
z `services/api/.venv`. [Rejestr odbioru](verification.json) zawiera pełne SHA,
checksums, konfigurację, wyniki i rzeczywiste komendy CLI.
[Kontrakt i uruchomienie](../../../../reference/chronological-inventory.md)
opisują aktualne zachowanie. Następny zakres to **06.5 — snapshoty i stockout truth**.

## Działający przebieg

Proces `chronological-shared-stock-1.0.0` łączy opening, dostawy, sprzedaż,
kwalifikowane zwroty i jawne write-offs/transfers/adjustments. Wszystkie zdarzenia
fizyczne mają porządek UTC timestamp/sequence; review następuje po zdarzeniach
w swoim cutoff. Jeden fizyczny zapas jest konsumowany kolejno przez kanały.
Arrival tworzy sale i wydanie tylko dla dodatniej realizacji;
`observed=min(latent,physical_available)`, pozostała ilość pozostaje private truth.

Historyczny fulfillment uwzględnia półotwarty okres dat i availability wersji.
Brak mappingu nie prowadzi do fallback. Zwroty odnoszą się do pierwotnej sale,
ceny i warehouse; wszystkie dispositions razem nie przekraczają zakupionej ilości.
Accepted zwiększa zapas, rejected daje refund bez restock.
MVP ma `reservation_policy=none` i natychmiastowy częściowy fulfillment.

Review korzysta z dostępnego ledgeru, znanych ofert i outstanding zamówień.
Coverage pochodzi z rzeczywiście przetworzonych okien, także bez sprzedaży.
Przyszłe popyt/realizacja nie są wejściami polityki. Fizycznie przyjęta dostawa
może być sprzedana przed jej ingestion/availability; dostępność późniejszej
sale czeka wtedy na receipt. Ta sama przyczynowość obowiązuje zwroty i transfery.
Unreceived tail pozostaje poza operational stock.

Niezależny walidator wymaga dokładnej bijekcji receipts, sales i accepted returns
z ruchami ledgeru, właściwego routingu, ilości, czasów i revenue/refund.
Private evaluator odtwarza stan przed arrival z fizycznych ruchów i uzgadnia
censoring oraz kompletność outcomes względem wszystkich wejściowych arrivals.

Fixture obejmuje jeden produkt, dwa warehouses i sześć arrivals w oknie dziesięciu
dni. Pierwsze dwa kanały realizują 6 i 2 sztuki ze wspólnego opening 8.
Normal supply daje 3 orders, 3 receipts i 45 przyjętych sztuk; 5 sales realizuje
25 z 29 żądanych sztuk, lost sales wynosi 4. Dwa zwroty dają refund 5.00/2.50 PLN,
tylko pierwszy przywraca 2 sztuki. Końcowy stan wynosi 24/6 i uzgadnia wszystkie
ruchy. Poor supply daje 4 partial/delayed receipts, 22 przyjęte sztuki,
10 zrealizowanych i 19 utraconych; pierwsze dwa reviews pozostają identyczne.

## Weryfikacja

- **485 testów `data/tests`, zero błędów i pominięć**, w tym 89 nowych.
  Pełna regresja obejmuje ledger, dostawy, reorder, source, Parquet,
  snapshot/export/handoff i istniejącą bramkę cross-repo.
- Przypadki obejmują shared stock, timestamp/sequence ties, historical mapping,
  future corrections, return quality/price/quantity/location, partial supply,
  transit, causal availability, nieznane fakty, zero demand i zero stock.
  Celowo uszkodzony wynik nie przechodzi niezależnego reconciliation;
  także arrival bez sprzedaży nie może zniknąć z truth.
- **19 rzeczywistych przypadków CLI na commicie implementacji**: normal/repeat,
  poor supply, no demand, zero stock, end tail, future demand i late sale,
  trzy `not_ready` oraz osiem celowo błędnych kontraktów/procesów.
  Statusy i exit 0/1 odpowiadają oczekiwaniom. Powtórny run zachowuje oba hashes.
- Ruff check/format i mypy `--follow-imports=silent` przechodzą dla 18 plików
  pakietu inventory. Nowy test jest sformatowany; trzy opublikowane schematy
  odpowiadają ścisłym modelom runtime.
- Oba dotychczasowe smoke wykonano po dwa razy: zachowane source IDs,
  po 46 hard gates i identyczne bajty CSV. Fingerprint domyślnego generatora
  jest niezmieniony względem `68fe5d9`; świeże demo zachowuje 17 CSV,
  a 19 śledzonych plików demo pozostaje zgodne z baseline.
- Pomiar samego małego fixture CLI: **0.0166 s / peak RSS 41.52 MiB**.
  Nie jest to benchmark chronologicznego generatora na standardowych smoke,
  dev lub training. Rejestr zachowuje dokładny pomiar i granicę jego zakresu.

## Granice odbioru

Symulator działa na jawnych oddzielnych wejściach. Domyślny source 2.6 nie
korzysta jeszcze z nowej ścieżki; integracja panelu, cen, koszyków i eksportu
należy do 06.6. Końcowe salda są diagnostyką, bez deklarowania snapshotów
lub epizodów stockout. Te artefakty powstaną w 06.5.

`inventory_ready=false`, DATA-06 i pełne source/readiness gates pozostają otwarte.
Nie opublikowano nowego source/curated, nie przepisano metryk modeli.
Rezerwacje, backorders, trwałe failure/cancellation i approval nie są wdrożone.
Pełny raport zawiera oddzielną simulation truth i nie jest eksportem API/cech.
Niedojrzały tail nie kwalifikuje przyszłych etykiet modelu stockout.

Kod, schematy, fixtures i testy są w commicie implementacji; osobny commit
dokumentacji zawiera odbiór i aktualny plan. Pełne raporty CLI/JUnit/compatibility
pozostają pod ignorowanym `ci-cd/reports/data/`; rejestr w Git zapisuje wyniki
i checksums. Nie wykonano zdalnego Required CI ani publikacji AI 06 na main.
