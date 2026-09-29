# Polityka uzupełniania AI 06.3

**Zakres:** działająca polityka przeglądu zapasu i osobna symulacja realizacji
dostaw na małym fixture. Wykorzystuje [ledger 06.1](inventory-ledger.md)
i [kontrakt dostaw 06.2](replenishment.md). Historyczny source 2.6
zachowuje własny kontrakt zgodności; domyślny source 2.7 korzysta z tych modułów. [Symulator 06.4](chronological-inventory.md)
korzysta z nich na osobnym scenariuszu. [Projekcje 06.5](inventory-projections.md)
tworzą snapshoty i stockout truth; integracja i publikacja mają [końcowy odbiór AI 06](../evidence/ai/06/final/README.md).

## Konfiguracja i decyzja

[Model konfiguracji](../../data/inventory/reorder_contract.py) i
[schemat](../../data/contracts/reorder_config.v1.schema.json) wymagają jawnych
parametrów dla każdej fizycznej pary produkt/stock location: reorder point,
safety stock, review cadence w dniach, długość historii oraz policy MOQ.
Konfiguracja ma wersję, UTC review anchor i czasy known/available.
Nie ma niejawnych rozmiarów ani domyślnych parametrów. Review następuje dokładnie
co cadence od anchor; reader nie zaokrągla timestampu do najbliższej doby.

[Polityka](../../data/inventory/reorder.py) `periodic-review-stock-position-1.0.0`
korzysta wyłącznie z faktów dostępnych w origin. Dla każdej fizycznej pozycji:

```text
stock_position = available_qty + suma znanego outstanding zamówień
rate = znana liczba sprzedanych sztuk / history_window_days
target = max(reorder_point + safety_stock,
             safety_stock + ceil(rate * (quoted_lead_time_days + review_cadence_days)))
effective_moq = max(policy MOQ, MOQ wybranego dostawcy)
order_qty = max(target - stock_position, effective_moq)
```

Zamówienie powstaje tylko przy `stock_position <= reorder_point` oraz dodatnim
deficycie do target. Zaokrąglenie w górę używa arytmetyki całkowitej.
MOQ jest dolnym limitem, bez zaokrąglania do jego wielokrotności.
Najpierw wybierana jest aktywna, obowiązująca i znana oferta według priorytetu,
supplier ID i quote ID, zgodnie z 06.2. Koszt ani niewidoczna reliability
nie zmieniają tej reguły. Quote wyznacza pierwotny obiecany termin.

Każda decyzja raportuje wykorzystany stan, observed sales, coverage ID,
ofertę, quoted lead time, resolved MOQ, target i ilość. Decyzja i order mają
deterministyczne UUID z konfiguracji, scope i origin. Natychmiastowe utworzenie
order jest jawne: ordered/ingested/available = origin, a plan v1 zachowuje te
same czasy. Powtórny review po dopisaniu order zwraca `already_ordered`.
Kolejny origin uwzględnia pozostałą ilość; częściowe przyjęcie przesuwa ją do
on-hand bez podwojenia stock position. Przeterminowane, nadal otwarte zamówienie
pozostaje outstanding; anulowania nie są implementowane.

## Historia, zero i brak danych

Średnia obejmuje znane ruchy `sale` w oknie `(origin-N dni, origin]`,
zagregowane dla fizycznego stocku. Nie ma kopii salda lub osobnego zamówienia
na każdy kanał. Returns nie są ujemnym popytem w tej formule.

[Kontrakt coverage](../../data/contracts/inventory_history_coverage.v1.schema.json)
deklaruje pokrycie strumienia obserwowanego ledgeru, jego przedział, availability
i provenance. Dowód musi pokrywać całe okno i być dostępny w origin; nie może
deklarować historii sprzed opening. To deklaracja pokrycia danych operacyjnych,
bez dostępu do latent demand i bez obietnicy znajomości późniejszych zdarzeń
lub korekt. Symulator 06.4 wyprowadza ją z rzeczywiście przetworzonych
okien, a nie z maksimum timestampu w sparse sprzedaży.

Bez coverage wynik ma `history_missing`, a liczba sprzedaży pozostaje null.
Bez znanej konfiguracji, opening lub oferty występuje odpowiednio
`config_unavailable`, `inventory_unknown`, `supplier_missing`. CLI zwraca wtedy
`not_ready` i exit 1. Zwykłe `not_due`, `no_order` i `already_ordered` są poprawnymi
decyzjami. Znana pełna historia bez sprzedaży daje rate zero; przy zerowym
floor/safety stock nie tworzy zamówienia. Późna sprzedaż lub receipt nie zmienia
decyzji odtworzonej dla wcześniejszego cutoff.

## Realizacja dostaw i truth

[Osobny moduł generatora](../../data/inventory/supplier_fulfillment.py) ma
[jawną konfigurację](../../data/contracts/supplier_fulfillment_config.v1.schema.json)
`supplier-fulfillment-config-1.0.0`, oznaczoną `simulation_truth`.
Wszystkie parametry są wymagane: seed, rozkład lead time, min/max dni,
disruption delay, partial fraction/gap oraz opóźnienia ingestion/availability.
Prawdziwe mean/std i reliability pochodzą z oddzielnego kontraktu supplier truth.

Proces `supplier-fulfillment-two-point-1.0.0` wybiera deterministycznie
`mean - std` lub `mean + std`, z równym prawdopodobieństwem przed zaokrągleniem.
Zaokrągla w górę do dni i ogranicza do min/max. Mean/std opisują rozkład bazowy;
clamping i zaokrąglenie mogą zmienić końcową średnią/odchylenie.
Reliability jest prawdopodobieństwem dostawy bez disruption, a nie gwarancją
zgodności z quoted terminem. Disruption dodaje jawny delay i rozdziela ilość
na dwie dodatnie części według partial fraction, z osobnym gap. Jedna sztuka
pozostaje jednym opóźnionym przyjęciem. Całość jest ostatecznie dostarczana;
permanent failure/cancellation nie są częścią tego procesu.

Losowania są SHA-256 keyed przez wersję, seed, order ID i cel losowania,
bez współdzielonego RNG zależnego od liczby innych zamówień. Porównanie
reliability i podział ilości używają dokładnych ułamków. Receipt IDs obejmują
order, konfigurację i supplier truth; zmiana parametrów nie nadpisuje tej
samej realizacji. Sequence przydziela caller bez kolizji z ledgerem.

Nie zapisujemy przyszłego rzeczywistego terminu jako wersji planu znanej przy
zamawianiu. Plan v1 pochodzi z quote; późniejsze komunikaty dostawcy można
dopisać przez 06.2 z własnymi czasami availability. Nowy moduł nie generuje
takich komunikatów ani nie zna przyszłego popytu. Zmiana seeda/truth zmienia
realizację, a przy tych samych dostępnych faktach pozostawia decyzję niezmienną.

## Uruchomienie i granice

```bash
services/api/.venv/bin/python -m data.inventory.run_reorder \
  --supply data/tests/fixtures/reorder-supply-v1.json \
  --ledger data/tests/fixtures/reorder-ledger-v1.json \
  --config data/tests/fixtures/reorder-config-v1.json \
  --coverage data/tests/fixtures/inventory-history-coverage-v1.json \
  --fulfillment-config data/tests/fixtures/supplier-fulfillment-config-v1.json \
  --supplier-truth data/tests/fixtures/supplier-simulation-truth-v1.json \
  --origin 2026-07-03T00:00:00Z \
  --output ci-cd/reports/data/ai06-03/reorder.json
```

Fixture ma jeden produkt i dwa magazyny: opening 8/0, znaną sprzedaż 4,
stan w origin 4/0 i historię dwóch dni. Przy reorder point 5, safety 3,
cadence 1 i quoted lead 2 target wynosi 9/8; zamówienia wynoszą 5/8 sztuk.
To jednorazowy przegląd, bez symulacji następnych dni sprzedaży.

Raport oddziela `operational` od `simulation_truth`. Pierwsza część zawiera
decyzje, nowe orders i znane plany; druga parametry, losowania i przyszłe
zaplanowane receipts. Pełny raport jest artefaktem generatora/ewaluacji,
nie wejściem feature buildera lub API. Hash każdej części jest osobny;
requested/effective config, checksums i code provenance są jawne.
Runner waliduje połączony book, projekcję receipts i pełny ledger przez 06.2
oraz potwierdza, że przyszłe przyjęcia nie zmieniają salda w origin.

[Odbiór 06.3](../evidence/ai/06/06.3/README.md) podaje testy i rzeczywiste CLI.
[Odbiór symulatora 06.4](../evidence/ai/06/06.4/README.md) obejmuje wielodniowe
wykonanie, shared stock, routing i zwroty. [Projekcje 06.5](inventory-projections.md)
dodają snapshoty i epizody; do [06.6](../plans/ai/etapy/06-inventory-ledger.md)
pozostają integracja oraz nowa publikacja i readiness.
Pełną publikację potwierdza [końcowy odbiór AI 06](../evidence/ai/06/final/README.md).
