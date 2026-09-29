# Kontrakt ledgeru zapasu AI 06.1

**Zakres:** działający kontrakt, walidacja, jednorazowe opening, odtwarzanie salda
i adapter do dotychczasowego CSV. Generator source 2.6 nie używa jeszcze ledgeru;
`inventory_ready=false`. [Dostawcy i receipt reconciliation 06.2](replenishment.md)
rozszerzają ten kontrakt na osobnym fixture. [Polityka 06.3](reorder-policy.md)
korzysta z dostępnego salda i historii. Chronologiczne ograniczanie sprzedaży,
snapshoty i nowa publikacja source należą do
[pozostałego AI 06](../plans/ai/etapy/06-inventory-ledger.md).

Źródłem struktury jest [strict runtime model](../../data/inventory/contract.py),
z którego powstaje [JSON Schema v1](../../data/contracts/inventory_ledger.v1.schema.json).
[Replay](../../data/inventory/ledger.py) sprawdza także reguły biznesowe.
Prawidłowy JSON nie zastępuje pełnej walidacji ledgeru.

## Opening, jednostka i porządek

Envelope `inventory-ledger-1.0.0` deklaruje katalog produktów i jednostek,
fizyczne stock locations, `inventory_scope` oraz wspólne `opening_at`.
Scope jest listą par produkt/fizyczna lokalizacja, bez kopii salda per kanał.
Każda para ma dokładnie jeden ruch `opening_stock`, również przy stanie zero.
Nie ma osobnego salda początkowego dodawanego drugi raz. Późniejszy snapshot
nie jest opening. Brak opening lub zdublowane otwarcie kończy walidację błędem.

Ilość to signed integer w jednostce katalogowego produktu; adapter nie przelicza
opakowań, masy ani objętości. Bools, floats i tekstowe liczby są odrzucane.
Ruch ma `inventory_event_id`, produkt, stock location, `quantity_delta`, jednostkę,
trzy czasy, `sequence`, `source_process` i `source_reference`; transfer/supplier/order
IDs mają jawne UUID albo null. Nieznane pola są odrzucane.

| Ruch | Legalna ilość | Proces |
|---|---|---|
| `opening_stock` | ≥ 0 | opening |
| `replenishment_received`, `return_to_stock`, `transfer_in` | > 0 | replenishment, return, transfer |
| `sale`, `write_off`, `transfer_out` | < 0 | sale, write_off, transfer |
| `inventory_adjustment` | ≠ 0, signed | adjustment |

Ruchy porządkuje `(occurred_at, sequence)` po normalizacji UTC.
Para timestamp/sequence jest unikalna w całym ledgerze; UUID nie rozstrzyga
niejednoznacznej kolejności. Każdy prefix ma nieujemne saldo. Późniejsze
adjustment nie może ukryć wcześniejszego overspend. `opening_stock` ustala saldo
raz; każdy kolejny ruch dodaje wyłącznie `quantity_delta`.

## Dostępność wiedzy i transit

Wymagane jest `occurred_at <= ingested_at <= available_at`, z jawnym UTC
i dokładnością do mikrosekund. Odczyt z `known_at` dopuszcza tylko fakty dostępne
w tej chwili i nie korzysta z przyszłego movement. Odczyt bez `known_at` opisuje
fizyczny proces według wszystkich faktów wejściowych; nie jest historyczną cechą.

Przed znanym opening stan ma `not_available` i nulls, a nie wymyślone zero.
Znany sale bez znanego opening albo ujemny prefix dostępnych faktów jest błędem;
reader nie uzupełnia go przyszłym receipt. Nie potwierdza to jeszcze kompletności
strumienia ani source readiness. Rezerwacje nie są implementowane:
`reservation_policy=none`, `reserved_qty=0`, `available_qty=on_hand` dla znanego salda.

Kompletny transfer ma dokładnie jeden outbound i inbound z tym samym transfer ID,
produktem, jednostką i równą ilością, pomiędzy różnymi lokalizacjami. Inbound
następuje po outbound w kolejności fizycznej i nie jest dostępny wcześniej.
Między ruchami `transit_at` pokazuje przenoszoną ilość, której nie przypisuje
do docelowego magazynu. Odczyt wcześniejszego origin zachowuje stan przed
przyjęciem albo późnym ingestion. Obsługa niedokończonych transferów jako
wejścia strumieniowego wymaga późniejszego kontraktu; kompletny fixture nie
akceptuje brakującej pary.

## Adapter i uruchomienie

[Adapter](../../data/inventory/legacy.py) ma wersję
`inventory-ledger-to-legacy-1.0.0`. Zachowuje istniejące kolumny `stock_movements`;
`opening_stock` mapuje na `initial_stock`, receipt na `replenishment`.
Stock location ID i jawny kod przechodzą do warehouse ID/code, bez modulo
lub fallback. `created_at` jest projekcją `ingested_at`.
Format legacy pomija availability, sequence i część provenance; nie można go
uznać za pełny ledger v1 ani odzyskać z niego brakujących czasów. Adapter nie
importuje starych tygodniowych snapshotów jako nowych otwarć.

Z katalogu głównego repo:

```bash
services/api/.venv/bin/python -m data.inventory.verify \
  --input data/tests/fixtures/inventory-ledger-v1.json \
  --occurred-through 2026-07-03T23:59:59Z \
  --known-at 2026-07-03T23:59:59Z \
  --output ci-cd/reports/data/ai06-01-ledger.json
```

[Fixture](../../data/tests/fixtures/inventory-ledger-v1.json) ma jeden produkt,
dwa magazyny, dwa opening i dziewięć ruchów obejmujących osiem typów.
W końcowym stanie WH-0001 ma 8 sztuk, WH-0002 ma 3; po outbound, przed inbound,
3 sztuki są w tranzycie. CLI zwraca exit 0 dla poprawnego ledgeru, exit 1
i raport `failed` dla błędnego kontraktu lub bilansu.

[Odbiór 06.1](../evidence/ai/06/06.1/README.md) podaje testy i provenance.
Sam walidator ledgeru nie sprawdza encji supplier/order/receipt;
[walidator 06.2](replenishment.md) dodaje to uzgodnienie.
[Symulator 06.4](chronological-inventory.md) uzgadnia także historyczny
fulfillment konkretnej sprzedaży i return eligibility.
[Projekcje 06.5](inventory-projections.md) uzgadniają snapshoty i epizody stockout.
Integracja generatora i pełny odbiór źródła pozostają wymagane przed `inventory_ready=true`.
