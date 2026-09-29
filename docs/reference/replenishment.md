# Dostawcy i przyjęcia AI 06.2

**Zakres:** kontrakt dostawców, ofert, zamówień, wersji terminów i rzeczywistych
przyjęć oraz uzgodnienie z [ledgerem 06.1](inventory-ledger.md).
Generator source 2.6 nie korzysta jeszcze z tych encji; `inventory_ready=false`.
Następny zakres to deterministyczna polityka uzupełniania **06.3**.

## Kontrakty i podział wiedzy

[Model runtime](../../data/inventory/replenishment_contract.py) generuje
[JSON Schema](../../data/contracts/replenishment.v1.schema.json) dla envelope
`replenishment-1.0.0`. [Reader i walidator](../../data/inventory/replenishment.py)
sprawdzają także klucze obce, czas, okresy ofert, MOQ oraz sumę przyjęć.
Sam schemat JSON nie zastępuje tych reguł biznesowych.

Supplier ma UUID, unikalny kod, kraj PL/DE, status active/inactive, MOQ i czas
dostępności metadanych. Oferta `product_suppliers` wiąże produkt i dostawcę:
jednostka katalogu, dodatni koszt jako decimal string z dwoma miejscami,
waluta PLN/EUR, dodatni priorytet i okres `[effective_from,effective_to)`.
Okresy tego samego produktu/dostawcy nie mogą się nakładać. MOQ jest minimalną
ilością, a nie wymaganiem jej wielokrotności. Kontrakt nie przelicza jednostek
ani walut. Lookup pomija nieaktywnego lub nieznanego dostawcę i niedostępną
ofertę; przy braku kwalifikującej się oferty zwraca pusty wynik.

Operacyjny lead time ma `lead_time_basis=supplier_quote`, quote reference
i własne `known_at`, `ingested_at`, `available_at`. Musi być dostępny przed
złożeniem zamówienia. Prawdziwa reliability i mean/std lead time symulatora są
oddzielnym [kontraktem truth](../../data/contracts/supplier_simulation_truth.v1.schema.json),
walidowanym przez [moduł symulacji](../../data/inventory/supplier_truth.py).
Reliability mieści się w `[0,1]`, mean/std są nieujemne; wartości są decimal
strings. Truth musi dokładnie pokrywać katalog dostawców. Te pola są odrzucane
w każdej encji operacyjnej. Reader i CLI nie przyjmują ani nie wczytują truth.

## Zamówienia i historia terminów

Zamówienie wskazuje konkretną ofertę, produkt, dostawcę i fizyczną lokalizację
docelową. Zachowuje ilość, czas zamówienia, pierwotnie obiecany termin oraz
provenance. Nie może korzystać z przyszłej oferty, nieaktywnego dostawcy,
niezgodnej jednostki, nieważnego okresu ani ilości poniżej MOQ.

Surowy rekord zamówienia ma niezmienny `status=ordered`: opisuje jego utworzenie.
`orders_at(known_at)` wylicza stan z dostępnych w cutoff przyjęć:
`ordered`, `partially_received` lub `received`, ilość przyjętą i pozostałą.
Nie przechowuje dzisiejszego końcowego statusu jako historycznej cechy.
Anulowanie i workflow zatwierdzania nie są częścią tego zakresu.

Pierwszy `delivery_plan_versions` dokładnie odpowiada pierwotnemu terminowi
i czasom zamówienia. Każda zmiana tworzy nowy UUID i kolejną wersję od 1,
bez luk, z zachowaniem chronologii wiedzy i availability. Reader wybiera
ostatnią wersję dostępną w cutoff; późniejsza informacja o opóźnieniu nie
zmienia wcześniejszego origin. Wszystkie timestampy wymagają poprawnego UTC
z dokładnością najwyżej do mikrosekund.

## Rzeczywiste przyjęcia i zapas

Receipt wskazuje zamówienie, produkt, dostawcę, destination, jednostkę,
rzeczywistą dodatnią ilość, `received_at`, ingestion/availability, sequence
oraz dokument przyjęcia. Obowiązuje czas biznesowy ≤ ingestion ≤ availability;
receipt nie może poprzedzać zamówienia ani stać się dostępny przed nim.
`over_receipt_policy=reject`: suma wszystkich częściowych przyjęć nie przekracza
zamówienia. Opóźnione przyjęcie jest poprawnym faktem; obiecany termin nie
nakłada fałszywego ograniczenia na jego rzeczywisty czas.

`receipt_movements()` tworzy deterministyczny ruch `replenishment_received`
wyłącznie z rzeczywistej ilości receipt. Order i plan nie zwiększają zapasu.
Ruch zachowuje czasy, sequence, supplier/order IDs i receipt UUID jako
`source_reference`; ten receipt prowadzi dalej do dokumentu przyjęcia.

`reconcile_ledger()` wymaga dokładnie jednego identycznego ruchu dla każdego
receipt i żadnych dodatkowych replenishments. Porównuje również ilość, czasy,
provenance i UUID; sprawdza zgodność destination code, scope i jednostki ledgeru,
także dla zamówienia bez przyjęć. Generator musi przydzielić sequence bez kolizji
z innymi ruchami; pełny ledger egzekwuje globalny porządek timestamp/sequence.

## Uruchomienie i fixture

Z katalogu głównego repo:

```bash
services/api/.venv/bin/python -m data.inventory.verify_replenishment \
  --input data/tests/fixtures/replenishment-v1.json \
  --ledger data/tests/fixtures/replenishment-ledger-v1.json \
  --known-at 2026-07-03T10:03:00Z \
  --output ci-cd/reports/data/ai06-02-supply.json
```

Fixture zamawia 12 sztuk, odbiera 5 dnia 3 lipca i pozostałe 7 dnia 6 lipca.
Pierwszy termin to 3 lipca; informacja o zmianie na 5 lipca jest dostępna
4 lipca o 09:02 UTC. Druga część dociera po zmienionym terminie.
Opening obu magazynów wynosi zero. W cutoff polecenia saldo WH-0001 wynosi
5, WH-0002 zero; status jest częściowy, outstanding 7, plan nadal w wersji 1.
Po dostępności drugiego przyjęcia saldo wynosi 12/0 i status `received`.

CLI zwraca exit 0 i raport `passed` albo exit 1 i raport `failed`.
Raport zachowuje checksums, znane zamówienia, salda, reconciliation i provenance
kodu. [Odbiór 06.2](../evidence/ai/06/06.2/README.md) podaje wyniki kontroli.
Polityka reorder, realizacja losowa dostaw, symulator wspólnego zapasu,
fulfillment sprzedaży, return eligibility, snapshoty i publikacja nowego source
nadal należą do [pozostałego AI 06](../plans/ai/etapy/06-inventory-ledger.md).
