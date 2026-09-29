# Chronologiczny zapas AI 06.4

[Symulator](../../data/inventory/simulator.py) łączy [ledger](inventory-ledger.md),
[dostawy](replenishment.md) i [politykę przeglądu](reorder-policy.md) w wykonywalny
przebieg sprzedaży ograniczonej wspólnym zapasem. Działa na osobnym scenariuszu;
domyślny generator source 2.6 nadal korzysta z dotychczasowej ścieżki.
`inventory_ready=false`. [Odbiór](../evidence/ai/06/06.4/README.md) zawiera
wyniki i wersję kodu. Następny zakres to 06.5: snapshoty i epizody stockout.

## Wejście i kolejność

[Kontrakt scenariusza](../../data/contracts/chronological_scenario.v1.schema.json)
`chronological-scenario-1.0.0` wymaga jawnej konfiguracji procesu
`chronological-shared-stock-1.0.0`. Początek i koniec są UTC; zdarzenia fizyczne
należą do `[start,end)`, przeglądy mogą odbyć się także dokładnie w `end`.
Początkowy ledger zawiera wyłącznie jednorazowe opening w `start`, a book
dostaw nie zawiera zamówień ani przyjęć. Scope polityki dokładnie pokrywa ledger.
Anchor musi pozwolić zebrać pełne okno historii i wykonać co najmniej jeden review.

Zdarzenia receipts, returns, popytu i jawnych actions są sortowane po czasie
biznesowym i unikalnym `sequence`. Typ nie nadpisuje kolejności intraday.
Review odbywa się po wszystkich zdarzeniach fizycznych w swoim timestampie;
reguły cadence są nadal egzekwowane przez politykę 06.3. Sequence generowanego
receipt jest kolejnym numerem po wszystkich zadeklarowanych zdarzeniach w tym
samym timestampie i wcześniejszych receipts w kolejce. Przy identycznym czasie
zadeklarowany arrival może więc poprzedzać nowo wygenerowany receipt.
Ta reguła jest częścią wersji procesu, bez ukrytego pierwszeństwa dostawy.

Opening, receipts i accepted returns zmieniają jeden fizyczny stan produktu
w stock location. Write-off, transfer i adjustment wymagają rzeczywistego,
jawnego dokumentu w scenariuszu; symulator nie dodaje korekt równoważących.
Transfer wymaga obu stron i ujawnia ilość w drodze między outbound a inbound.
Ujemny fizyczny stan, kolizja kluczy lub niekompletna para blokuje wykonanie.

## Fulfillment i sprzedaż

[Historyczne mapowanie](../../data/contracts/inventory_fulfillment_routes.v1.schema.json)
wiąże selling location/channel z fizycznym warehouse. Okres dat jest półotwarty
w UTC, a wersja musi być dostępna w chwili sprzedaży. Korekta ma ten sam okres,
kolejną wersję i niemalejącą availability; częściowo nakładające się okresy są
odrzucane. [Resolver](../../data/inventory/fulfillment_routes.py) wybiera najwyższą
znaną wersję. Brak mappingu przerywa run, także dla arrival bez sprzedaży.
Nie przechodzi automatycznie na inny warehouse.

MVP deklaruje `reservation_policy=none` i `instant_partial_fulfillment`.
Nie ma oddzielnego reserve/release ani podwójnego pomniejszenia zapasu.

```text
observed_quantity = min(latent_quantity, physical_available_before_arrival)
lost_sales_quantity = latent_quantity - observed_quantity
```

Dodatnia realizacja tworzy jeden order sprzedażowy, jedną sale i jedno wydanie
ledgeru. Zero nie tworzy fikcyjnej transakcji. Kolejne kanały korzystają z już
pomniejszonego wspólnego stanu. Cena dodatnia, jednostka i waluta są jawne;
revenue/refund liczone są w całkowitych groszach. Zewnętrzna ścieżka cen,
koszyków i panelu source 2.6 zostanie połączona z tym przebiegiem w 06.6.

## Zwroty i czas wiedzy

Zwrot musi wskazywać wcześniejszą, rzeczywiście zrealizowaną sale. Wszystkie
dispositions razem nie przekraczają zakupionej ilości. `accepted` tworzy dodatni
`return_to_stock`; `rejected` tworzy zwrot finansowy bez restock. Produkt,
jednostka i warehouse pochodzą z pierwotnego fulfillment, również po zmianie
routingu. Refund korzysta z pierwotnej ceny, bez późniejszego repricing.
Nowy warehouse dla zwrotu wymagałby osobnej, jawnej polityki i ruchów.

Stan fizyczny zmienia się w czasie biznesowym. Review widzi wyłącznie fakty
z `available_at <= origin`, historyczne quote i znane pozostałe zamówienia.
Nie zna latent demand ani przyszłego rzeczywistego terminu dostawy.
Coverage powstaje z przetworzonego przedziału zegara symulacji, także w dniach
bez sprzedaży; nie jest wyprowadzane z maksimum sparse transakcji.
Nie deklaruje wiedzy o opóźnionych faktach lub przyszłych korektach.

Availability kolejnego ruchu w fizycznej pozycji nie może poprzedzać
availability wcześniejszych ruchów. Sale zużywająca fizycznie przyjęty,
jeszcze nieznany receipt czeka z dostępnością na ten receipt; return także
na pierwotną sale, a transfer-in na outbound. Ingestion pozostaje osobnym
czasem zdarzenia. Takie opóźnienie zachowuje przyczynowość i nie tworzy
ujemnego prefiksu znanego ledgeru.

Receipt poza oknem pozostaje w `simulation_truth.scheduled_receipt_tail`:
nie jest wykonanym przyjęciem i nie zwiększa zapasu. Plan v1 nadal pochodzi
z quote, bez przepisania przyszłej realizacji na historycznie znany ETA.

## Uruchomienie i uzgodnienie

Z katalogu głównego repo:

```bash
services/api/.venv/bin/python -m data.inventory.run_simulation \
  --scenario data/tests/fixtures/chronological-scenario-v1.json \
  --ledger data/tests/fixtures/chronological-opening-v1.json \
  --supply data/tests/fixtures/reorder-supply-v1.json \
  --policy data/tests/fixtures/reorder-config-v1.json \
  --fulfillment-config data/tests/fixtures/supplier-fulfillment-config-v1.json \
  --supplier-truth data/tests/fixtures/chronological-supplier-truth-v1.json \
  --output ci-cd/reports/data/ai06-04/simulation.json
```

Raport oddziela wykonane dane `operational` od prywatnych outcomes popytu,
losowań dostaw i tailu w `simulation_truth`. Każda część ma osobny hash;
pełny raport generatora nie jest eksportem cech/API. Konfiguracja, checksums
wejść, runtime provenance, czas i peak RSS są jawne.

[Niezależne uzgodnienie](../../data/inventory/simulation_reconciliation.py)
sprawdza bijekcję receipts/sales/accepted returns z ruchami, historyczny routing,
ilości, czasy, provenance, revenue/refund i limit zwrotów.
Prywatny evaluator odtwarza stock przed każdym arrival z ledgeru, uzgadnia
censoring i sprawdza kompletność outcomes względem wejścia.
[Commerce Schema](../../data/contracts/inventory_commerce_output.v1.schema.json)
egzekwuje typy; reguły biznesowe pozostają w walidatorze.

CLI zwraca `passed`/exit 0, `not_ready`/exit 1 przy nieznanych danych potrzebnych
do review albo `failed`/exit 1 przy błędnym procesie/kontrakcie.
Końcowe salda są diagnostyką, nie odbiorem snapshotów 06.5.
Epizody stockout, source/readiness gates, nowa publikacja 03 oraz zależne oceny
04/05 pozostają poza tym zakresem. DATA-06 jest nadal otwarte.
