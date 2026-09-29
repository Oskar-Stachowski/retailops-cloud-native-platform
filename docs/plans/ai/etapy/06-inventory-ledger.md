# 06 — Zbuduj spójny zapas i dostawy

**Status: ukończony zakres AI 06. Repo: oba. Zależność: 03.**
[Końcowy audyt i odbiór](../../../evidence/ai/06/final/README.md) potwierdza
pełną ścieżkę source → qualification → snapshot → import → curated/as-of.
[Runbook](../../../reference/inventory-snapshots.md) opisuje komendy użytkowe;
[karta danych](../../../evidence/ai/06/final/dataset-card.md) podaje nowe IDs.

Ledger, wspólna fizyczna pula zapasu, sprzedaż, zwroty, dostawy i stockout wynikają
z jednego chronologicznego procesu. Źródło 2.7 ma 58 tabel i 36 bramek,
snapshot/curated 1.1 udostępniają 43 facts/plans z causal availability.
Prywatne parametry/outcomes i kwalifikacja labeli pozostają poza cechami.
Domyślne CLI profili AI używa 2.7; jawny `--source-version 2.6` zachowuje kompatybilność.
Demo/API i frozen dane nie są przepisywane. DATA-06 nie ma otwartych warunków.

## Granica ukończenia i dalsze zależności

AI 06 można ukończyć niezależnie od 04/05. Gotowość inventory dotyczy danych
oraz odebranego pipeline'u, a nie wytrenowanego modelu lub serving.
Przed 07/08 wymagane są ukończone 04/05 oraz forecast oceniony na nowych IDs
z tej ścieżki. Jeśli 04/05 jeszcze nie ukończono, będzie to pierwszy zgodny
odbiór na nowym źródle; wcześniejszych metryk nie przepisuje się na inne dane.
Model ryzyka stockout jest zakresem 08.

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
- Zmiana procesu symulacji tworzy nowe immutable dane, a istniejący snapshot 03 pozostaje nienaruszony. Zachować demo/API compatibility.

## Artefakty i Definition of Done

Schematy ledger/suppliers/replenishments/mapping, udokumentowana kolejność i polityka rezerwacji, passing/failing fixtures, reconciliations, source/curated manifests, inventory/lost-sales/stockout diagnostics, zaktualizowana dataset card oraz evidence ponownego uruchomienia03. Wydajność measured na smoke, a dev/training poza zwykłym CI.

Przejście do 07/08 wymaga, oprócz odbioru 06, zgodnych prognoz i lifecycle po ocenie 04/05 na nowym snapshotcie. Zaawansowane zakupy, optymalizacja dostawców i złożone transfer networks pozostają rozszerzeniem po portfolio v1.

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
Opublikuj NOWY snapshot przez ścieżkę 03 i zapisz readiness/evidence. Zgłoś obowiązkowe
ponowienie04/05 po zmianie źródeł i cech; nie aktualizuj starych wyników bez re-evaluacji.
Nie trenuj tu klasyfikatora08 i nie wdrażaj rozbudowanego procurement ani cloud.
```
