# 06. Zbuduj spójny zapas i dostawy

**Status: plan wdrożenia. Repo: RetailOps. Zależność: 03.**

Cel: uzyskać faktyczny wspólny ledger zapasu, z którego wynikają sprzedaż ograniczona dostępnością, dostawy, snapshoty i epizody stockout. Ten etap można rozwijać równolegle z04/05 po ukończeniu03. Model ryzyka powstaje później w08; samo przejście bramek źródłowych nie oznacza gotowego modelu.

Przeczytaj [dane i czas](../kontrakty/dane-i-czas.md), [profile i bramki](../kontrakty/profile-i-bramki.md) oraz manifest/snapshot/curated contracts03. Potwierdź mapowanie product/selling location/channel → fizyczna stock location. Aktualne legacy snapshoty oraz cykliczne `initial_stock` nie są pełnym ledgerem.

## Kolejność małych PR-ów

1. **Kontrakt ruchu i opening.** Dodać `inventory_event_id`, produkt, stock location, signed quantity, jednostkę, `occurred_at`, `ingested_at`, `available_at`, deterministic sequence, reference do źródłowego procesu oraz opcjonalny transfer/supplier/order ID. Wybrać jedną reprezentację otwarcia: początkowy balance albo pojedynczy opening movement. Snapshoty tygodniowe/dzienne nie generują kolejnych ruchów otwarcia. Jawnie wersjonować adapter legacy.
2. **Minimalni dostawcy i replenishment.** Encje `suppliers`, `product_suppliers`, `replenishment_orders` oraz receipts. Supplier: kod, kraj, status, reliability, mean/std lead time, MOQ. Product supplier: jednostkowy koszt, priorytet, okres obowiązywania. Order: product, supplier, destination, ordered quantity/time, expected delivery znane w danej wersji, status. Receipt: rzeczywista ilość/time, link do order i provenance. Umożliwić partial/delayed receipt; plan nie jest faktycznym przyjęciem.
3. **Deterministyczna polityka uzupełniania.** Parametry reorder point, safety stock, review cadence, MOQ i lead-time variation; wszystkie w effective config. Zamówienie powstaje na podstawie obserwowalnego stanu/historycznej sprzedaży, nie oracle przyszłego latent demand. Supplier reliability działa w procesie realizacji dostawy. Parametry prawdziwego rozkładu lead time/reliability symulatora są truth; do operational features dopuszcza się wyłącznie jawnie znane quoted lead time albo estymatę z historii sprzed cutoff, z pochodzeniem. Wersje planowanego terminu zachowują available time. Rozbudowany approval/procurement optimization nie należy do tego etapu.
4. **Chronologiczny symulator.** W każdej dobie zastosować wersjonowaną kolejność due receipts, kwalifikowanych returns/adjustments, arrival popytu i transakcji, wydania sprzedażowego, write-offs/transfers, zamknięcia i nowych zamówień. Jeśli występuje zdarzenie intraday, kolejność wynika z czasu i deterministic sequence, nie tylko typu. Jeden zasób wspólny kanałom jest konsumowany kolejno jeden raz. `observed_sales=min(latent_demand, available_inventory)`; niezaspokojony popyt i jego przyczyny pozostają truth.
5. **Snapshoty, rezerwacje i stockout truth.** Snapshot budować wyłącznie z ledgeru. MVP może jawnie ustalić `reserved_qty=0` i natychmiastowy fulfillment; nie deklarować działania rezerwacji. Jeżeli je wprowadzasz, zdefiniuj state machine reserve/release/fulfill, aby ta sama sprzedaż nie pomniejszała stanu dwa razy. Zwrot do sprzedaży ma jawne warunki jakości; nie każdy zwrot jest return_to_stock. Zdefiniuj epizod dostępności zero, jego początek/koniec i affected scopes; policz duration/lost-sales diagnostycznie. Zero przed origin należy później do `already_stockout`.
6. **Ponowna publikacja danych.** Rozszerzyć quality/realism/readiness, przeliczyć source dataset i eksport/import03. Dopiero po przejściu gates ustawić `inventory_ready=true`. Nowy proces censoringu zmienia source/curated IDs. Ponownie wykonać04/05 na nowych danych i zgodnym feature schema, zanim forecast zasili anomaly/stockout. Nie przepisywać wcześniejszych metryk modelu na nowy dataset.

## Minimalny zestaw ruchów i uzgodnienie

Obsłużyć `opening_stock`, `replenishment_received`, `sale`, `return_to_stock`, `write_off`, `transfer_in`, `transfer_out`, `inventory_adjustment`. Typ ruchu ma legalny znak i źródło; adjustment nie służy do cichego równoważenia błędów symulatora. Transfer ma wspólny `transfer_id`, równą ilość wyjścia/wejścia oraz, jeśli czas między nimi jest dodatni, jawny transit state. Inbound nie pojawia się przed outbound.

`closing_balance = opening_balance + sum(quantity_delta)` dla każdej product/stock location/doby. `available=on_hand-reserved` według wdrożonej polityki. Wspólnego magazynu nie przypisuje się niezależnie w pełnej ilości każdemu kanałowi. Fulfillment mapping ma okres obowiązywania oraz availability; brak mappingu to błąd/readiness missing. Join do cechy nie przechodzi na inny magazyn i nie bierze przyszłego snapshotu.

Stockout truth oznacza zdarzenie procesu zapasu; zwykły brak popytu i zero sprzedaży to inna sytuacja. Do przyszłego labelu08 wymagane jest pełne okno `(t,t+7 dni]`, polityka dojrzałości i dostępność outcomes. Tego labelu nie dołącza się do źródłowych cech API.

## Kontrole wymagane i negatywne

- 100% uzgodnionych product/location/date i snapshot=ledger balance; celowe podwojenie opening, brak movement albo błędny znak failują.
- Ten sam timestamp i powtórny seed dają identyczny porządek i stan końcowy. Współdzielony zapas dwóch kanałów nie pozwala łącznie sprzedać więcej niż dostępne sztuki.
- Każda sprzedaż ma dokładnie właściwe wydanie z właściwego fulfillment location; inny warehouse lub brak mappingu jest odrzucany.
- Partial receipt nie zwiększa stanu o pełne zamówienie; receipt przed order, over-receipt bez jawnej polityki i transfer bez pary/ujawnionego transit powodują failed gate.
- Odrzucony jakościowo zwrot nie zwiększa dostępnego zapasu; ilość zwrotów nie przekracza zakupionej; accepted return ma właściwy czas/location.
- Ledger nie produkuje nieuzasadnionego ujemnego stanu. Nie tworzyć stockout przez ustawienie przypadkowej flagi oderwanej od procesu.
- Plan dostawy known w origin może być cechą, rzeczywiste opóźnienie znane dopiero później — nie. Późny receipt lub correction nie zmienia historycznych cech.
- Supply-poor, supply-normal, partial/delayed receipt, no demand i zero-at-origin mają oddzielne fixtures. Readiness08 jest not_evaluable przy niedojrzałym tailu/braku klas, nie automatycznie passed.
- Zmiana procesu symulacji tworzy nowe immutable dane, a istniejący snapshot03 pozostaje nienaruszony. Zachować demo/API compatibility.

## Artefakty i Definition of Done

Schematy ledger/suppliers/replenishments/mapping, udokumentowana kolejność i polityka rezerwacji, passing/failing fixtures, reconciliations, source/curated manifests, inventory/lost-sales/stockout diagnostics, zaktualizowana dataset card oraz evidence ponownego uruchomienia03. Wydajność measured na smoke, a dev/training poza zwykłym CI.

Gotowość źródłowa do07/08 wymaga bramek powyżej, nowego snapshotu i zgodnych prognoz po ponownej ewaluacji04/05. Zaawansowane zakupy, optymalizacja dostawców i złożone transfer networks pozostają rozszerzeniem po portfolio v1.

## Prompt dla Codex

```text
W RetailOps wykonaj etap06 z etapy/06-inventory-ledger.md.
Przeczytaj README.md, architektura.md, kontrakty/dane-i-czas.md,
kontrakty/profile-i-bramki.md, kontrakty/ml-api-lifecycle.md oraz evidence03.
W małych PR-ach wdrażaj ledger, minimalnych suppliers/product_suppliers/replenishment
orders/receipts, deterministyczną reorder policy i chronologiczną wspólną pulę zapasu.
Opening licz jeden raz. Snapshot ma wynikać z ledgeru; nie koryguj błędów losowym adjustment.
Utrzymuj source/available time, mapping lokalizacji i truth poza cechami. Przetestuj
partial/delayed receipt, return eligibility, transfer, shared inventory i future fallback.
Opublikuj NOWY snapshot przez ścieżkę03 i zapisz readiness/evidence. Zgłoś obowiązkowe
ponowienie04/05 po zmianie źródeł i cech; nie aktualizuj starych wyników bez re-evaluacji.
Nie trenuj tu klasyfikatora08 i nie wdrażaj rozbudowanego procurement ani cloud.
```
