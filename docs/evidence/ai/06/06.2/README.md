# AI 06.2 — dostawcy, zamówienia i rzeczywiste przyjęcia

**Odbiór lokalny 29.09.2026 na branchu `ai/06-01-inventory-ledger`,
implementacja `8fd2e3f`.** Środowisko: macOS ARM64, Python z `services/api/.venv`.
[Rejestr odbioru](verification.json) wiąże commit, checksums, komendy,
rzeczywiste CLI i wyniki. [Kontrakt i uruchomienie](../../../../reference/replenishment.md)
opisują aktualne zachowanie. Następny zakres to **06.3 — polityka uzupełniania**.

## Działające zachowanie

Kontrakt `replenishment-1.0.0` obejmuje dostawców, oferty produktów, zamówienia,
niezmienne wersje obiecanego terminu i rzeczywiste receipts. Walidacja sprawdza
strict types, klucze obce, jednostkę, destination, dodatni koszt, priorytet,
niepokrywające się okresy ofert, MOQ i dostępność oferty przy zamawianiu.

Supplier reliability i prawdziwy mean/std lead time mają oddzielny kontrakt
`supplier-simulation-truth-1.0.0`. Są odrzucane w rekordach operacyjnych.
Operational reader korzysta z jawnego quote i jego provenance; nie ładuje truth.
Parametry realizacji dostaw zostaną użyte przez symulator w dalszym zakresie.

Surowy order opisuje utworzenie ze statusem `ordered`. Reader wylicza
`ordered` / `partially_received` / `received` i outstanding według przyjęć
dostępnych w cutoff. Wybiera również ostatnią dostępną wersję terminu.
Późniejsza zmiana planu lub ingestion receipt nie przepisuje wcześniejszego origin.

Fixture zamawia 12 sztuk, przyjmuje 5 oraz opóźnione 7. Ledger zaczyna od zero
w obu magazynach. Przed dostępnością pierwszej dostawy saldo wynosi zero,
po niej 5/0, a po dostępności drugiej 12/0. Sam order ani plan nie tworzą zapasu.
Reconciliation wymaga dokładnie jednego identycznego ledger movement na receipt;
brak, nadmiar, niewłaściwa ilość, czas, link, jednostka lub destination failują.
Łączne przyjęcia ponad zamówienie są odrzucane przez jawną politykę `reject`.

## Weryfikacja

- **324 testy `data/tests`, zero błędów i pominięć**, w tym 146 nowych testów
  dostaw i 89 testów ledgeru. Pełna regresja obejmuje wcześniejsze snapshot,
  eksport/handoff, Parquet i bramkę cross-repo.
- Nowe testy obejmują granice availability, partial/delayed receipts,
  nieznane order/quote bez future fallback, historię terminów, brak zamówień,
  pending order, sumę przyjęć, powiązania, unit/MOQ, UTC, deterministyczny
  porządek, immutability i izolację supplier truth.
- **15 rzeczywistych przypadków CLI** na commicie implementacji: odczyty
  przed/na availability przyjęć i zmiany terminu, pełne opóźnione przyjęcie,
  nieznane zamówienie, brak zamówień oraz negatywne próby over-receipt,
  receipt przed order, przyszłej oferty, truth w supplier, brakującego ruchu
  i użycia pełnej ilości zamówienia dla częściowej dostawy. Exit/report są zgodne.
- Ruff check/format i mypy `--follow-imports=silent` przechodzą dla dziewięciu
  plików pakietu inventory. Dwa nowe schematy JSON odpowiadają modelom runtime.
- Oba standardowe smoke wygenerowano dwukrotnie: 46 hard gates na każdy run,
  identyczne source IDs i bajty CSV. Fingerprint generatora pozostaje zgodny
  z bazą `68fe5d9` z main. Świeże demo zachowuje 17 CSV z przyjętego baseline’u;
  19 śledzonych plików demo również nie zmieniło się.

## Granice odbioru

To odbiór osobnego kontraktu i uzgodnienia, bez podłączenia do generatora 2.6.
`inventory_ready=false`, DATA-06 pozostaje otwarte. Nie ma nowego source,
snapshotu ani curated; wcześniejsze metryki modeli zachowują swój zakres danych.

Reorder policy i effective config, losowa realizacja dostaw, chronologiczna
wspólna pula zapasu, fulfillment sprzedaży, return eligibility, snapshoty
i końcowe source gates pozostają w [instrukcji AI 06](../../../../plans/ai/etapy/06-inventory-ledger.md).
Nie ma anulowania/approval workflow ani konwersji walut lub jednostek.
Nie wykonano zdalnego Required CI ani publikacji AI 06 na main.

Kod, schematy, fixtures i testy są w commicie implementacji. Osobny commit
dokumentacji zawiera ten odbiór. Pełne raporty CLI, zgodności i JUnit pozostają
w ignorowanym `ci-cd/reports/data/`; mały rejestr w Git zapisuje ich checksums
oraz wyniki na czystych plikach runtime.
