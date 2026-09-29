# AI 06.1 — kontrakt ruchów i jednorazowe opening

**Odbiór lokalny 29.09.2026 na branchu `ai/06-01-inventory-ledger`.**
Etap AI 06 jest w realizacji. [Odbiór symulatora 06.4](../06.4/README.md)
wskazuje aktualny punkt wznowienia: **06.5 — snapshoty i stockout truth**.
[Kontrakt i uruchomienie](../../../../reference/inventory-ledger.md)
opisują aktualne zachowanie. [Rejestr odbioru](verification.json) zapisuje commit
implementacji, fingerprints, fixture, rzeczywiste CLI i wyniki kontroli.

## Co działa

Wersja `inventory-ledger-1.0.0` ma jawny scope produkt/fizyczna lokalizacja,
jeden opening movement na parę, osiem typów ruchów, signed integers i UTC.
Ścisły model oraz JSON Schema odrzucają nieznane pola i wersje. Replay ma
deterministyczny timestamp/sequence, nieujemne prefixy i odczyt dostępnych faktów
według `available_at`; nieznany opening nie staje się zerem. Nadmiarowa precyzja
timestampu jest odrzucana zamiast obcinania cutoff.

Transfer jest uzgodnioną parą z jawnym transit. Fixture obejmuje dziewięć ruchów,
w tym dwa opening; saldo końcowe to 8 sztuk w WH-0001 i 3 w WH-0002.
Między outbound i inbound 3 sztuki pozostają w tranzycie.
Adapter `inventory-ledger-to-legacy-1.0.0` zachowuje dotychczasowe kolumny CSV,
bez rotacyjnego doboru warehouse i bez odtwarzania brakującej availability.

## Weryfikacja

- Testy ledgeru sprawdzają wszystkie typy, znaki, zero opening, duplicate/missing
  opening, overspend, kolejność przy tym samym czasie, unknown masters/unit,
  niepoprawne transfery, late facts, przyszły fallback i niezmienność wejścia.
- Pełna regresja `data/tests` obejmuje także wcześniejsze Parquet, immutable
  snapshot/export, handoff i bramkę cross-repo. Wyniki i liczby są w rejestrze.
- Lint, format i mypy obejmują nowy pakiet. Schemat zapisany w Git odpowiada
  dokładnie modelowi walidacji runtime; realne CLI zwraca właściwy exit/report.
- Oba standardowe profile AI są generowane dwukrotnie i odczytywane przez
  walidator source 2.6. Każdy przechodzi 46 hard gates, zachowuje source ID z
  [odbioru AI 03](../../03/03.6/dataset-card.md) i identyczne bajty CSV w powtórzeniu.
  Fingerprint wykonywanego generatora pozostaje zgodny z bazą `68fe5d9`.
- Świeża generacja demo zachowuje 17 CSV względem przyjętego baseline’u;
  19 śledzonych plików demo nie zmienia się. Śledzone demo jest przygotowanym
  zestawem aplikacji i nie jest porównywane ze świeżą generacją jako ten sam run.

## Granice odbioru

Ledger nie jest jeszcze podłączony do generatora ani publikowany jako nowy source
lub snapshot. `inventory_ready=false`, DATA-06 pozostaje otwarte. Źródło 2.6
zachowuje dotychczasowe IDs; wcześniejsze snapshoty i metryki modeli nie są zmieniane.

Ten odbiór 06.1 nie obejmował supplier/order/receipt reconciliation;
[odbiór 06.2](../06.2/README.md) sprawdza je odrębnie. Historyczny fulfillment
dla konkretnej sprzedaży, return eligibility, wspólne ograniczenie
sprzedaży, snapshoty i końcowe quality/readiness pozostają dalszymi zakresami AI 06.
Nie ma nowego zdalnego Required CI ani merge tego brancha na main.

Kod i testy są w commicie implementacji; osobny commit dokumentacji dodaje
ten odbiór. Duże dane, pełne raporty CLI i JUnit pozostają pod ignorowanym
`ci-cd/reports/data/`. Mały rejestr w Git zachowuje wyniki i checksums.
