# 06. Zbuduj spójny zapas i dostawy

**Status: w realizacji; 06.6b.1 ma lokalny odbiór 27 typowanych tabel inventory. Następny zakres: 06.6b.2 — integracja tabel z wersjonowanym domyślnym source i publikacja danych. Repo: RetailOps. Zależność: 03.**

Cel: uzyskać faktyczny wspólny ledger zapasu, z którego wynikają sprzedaż ograniczona dostępnością, dostawy, snapshoty i epizody stockout. Ten etap można rozwijać równolegle z04/05 po ukończeniu03. Model ryzyka powstaje później w08; samo przejście bramek źródłowych nie oznacza gotowego modelu.

Przeczytaj [dane i czas](../kontrakty/dane-i-czas.md), [profile i bramki](../kontrakty/profile-i-bramki.md), manifest/snapshot/curated contracts03 i [integrację koszyków 06.6a](../../../reference/source-inventory-commerce.md). Domyślny source 2.6 nadal nie publikuje nowego ledgeru; `inventory_ready=false` i DATA-06 pozostają otwarte.

## Obecny punkt integracji

[Polityka i proces dostaw 06.3](../../../reference/reorder-policy.md) mają
[lokalny odbiór](../../../evidence/ai/06/06.3/README.md). Zamówienie korzysta
wyłącznie z dostępnych faktów; seed i true lead-time/reliability sterują
oddzielną realizacją. [Chronologiczny symulator 06.4](../../../reference/chronological-inventory.md)
łączy te moduły z ograniczeniem sprzedaży, historycznym mappingiem i eligibility
zwrotów; [odbiór](../../../evidence/ai/06/06.4/README.md) dotyczy osobnego
scenariusza, bez przełączenia domyślnego generatora 2.6.
[Snapshoty i stockout truth 06.5](../../../reference/inventory-projections.md)
mają [lokalny odbiór](../../../evidence/ai/06/06.5/README.md): znany ledger,
osobne salda fizyczne, granice epizodów i lost-sales impacts oraz dojrzałość
diagnostycznych okien. Model 08 i pełna gotowość źródła pozostają poza tym odbiorem.

[Integracja 06.6a](../../../reference/source-inventory-commerce.md) wykonuje
koszyki popytu przez tę samą pulę fizycznego zapasu, przelicza ceny dla faktycznej
ilości i refundy dla faktycznych zakupów. Rozdziela finansową eligibility,
quality restock i ogon zwrotów, a panel/history/cohort korzystają z causal
availability. [Odbiór lokalny](../../../evidence/ai/06/06.6a/README.md) obejmuje
standardowe profile i niezależne uzgodnienie facts/ledger/snapshotów.
To kandydat z własnym execution ID, bez opublikowanego source/snapshot/curated.

[Kontrakt tabel 06.6b.1](../../../reference/inventory-source-tables.md) rozdziela
19 operational facts/plans i 8 private truth tables. Native CSV/Parquet
zachowuje typy, nulle, grain i historyczne availability; odczyt ponownie uzgadnia
cały proces oraz projekcje 06.5. [Odbiór lokalny](../../../evidence/ai/06/06.6b.1/README.md)
obejmuje powtórzenia profili i kontrolowane uszkodzenia. To nadal kandydat tabel;
kwalifikacja lifecycle/coverage modelu 08 ma `not_evaluated`.

## Następny zakres — 06.6b.2

1. Włączyć typowane inventory/supply/return-disposition tables w nowy domyślny source: konfiguracje, wersję, identity, manifesty i pełne quality/realism/readiness. Zachować czytniki 2.0–2.6 i niezmienne snapshoty 03 oraz demo/API compatibility.
2. Zakwalifikować lifecycle/coverage inventory i projekcje 06.5 w rzeczywistych source profiles, w tym no demand, zero stock, niedojrzały tail, przyszłe/niedostępne ruchy i supplier-poor. Sam pełny panel sprzedaży nie kwalifikuje labels 08.
3. Opublikować NOWY source/snapshot/curated przez rozszerzony exporter i importer03, z allowlistą operational facts, oddzielnym truth, typed parity, powtórzeniami oraz bramką cross-repo i pomiarem budżetu. Dopiero pełne gates pozwalają ustawić `inventory_ready=true` i zamknąć DATA-06.
4. Ponownie wykonać04/05 na nowych IDs i zgodnym feature schema, zanim forecast zasili anomaly/stockout. Nie przepisywać wcześniejszych metryk modelu na nowy dataset.

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
