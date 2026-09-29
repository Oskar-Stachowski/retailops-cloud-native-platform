# Chronologiczna realizacja koszyków źródłowych — AI 06.6a

Proces `source-inventory-commerce-1.0.0` łączy istniejący generator popytu,
cen i koszyków z [symulatorem wspólnego zapasu](chronological-inventory.md).
To wykonywalny kandydat integracji, z osobnym poleceniem i raportem.
Domyślny generator pozostaje source 2.6; ten raport nie jest nowym source
manifestem ani snapshotem AI. `source_ready=false`, `inventory_ready=false`
i `model_ready=false` dotyczą kandydata, do czasu pełnego odbioru publikacji.

## Wejście i przebieg

[Ścisły kontrakt konfiguracji](../../data/contracts/source_inventory_config.v1.schema.json)
oraz [przykład](../../data/tests/fixtures/source-inventory-config-v1.json)
określają opening, punkt zamówienia, safety stock, MOQ, cadence, okno historii,
ofertowy lead time i opóźnienia dostępności. Oddzielne pola truth określają
reliability, rozkład rzeczywistego lead time i partial/delayed fulfillment.
Seed dostaw musi być równy seedowi źródła. Za krótka obserwacja nie skraca
po cichu okna historii; jest błędem wejścia.

Istniejące nieograniczone koszyki stają się prywatnymi arrivals popytu.
Chronologiczny proces realizuje je przez historyczny routing i wspólną fizyczną
pulę zapasu. Opening powstaje raz na każdą zadeklarowaną parę product/stock
location, także przy ilości zero. Jego ilość jest jawną konfiguracją;
nie jest wyznaczana z przyszłego popytu ani uzupełniana kolejnymi opening.

Realizacja częściowa zachowuje oryginalny koszyk i ID pozycji, ale ma nowe ID
faktycznej sprzedaży. Resolver ponownie wycenia **zrealizowaną ilość** w czasie
oryginalnego zamówienia. Jedna sztuka pozostała z żądania dwóch nie dostaje
rabatu bundle z minimum dwóch. Pozycje o zerowej realizacji i puste koszyki
nie stają się sprzedażą. Kwota zamówienia wynika z faktycznych pozycji;
każda z nich ma dokładnie właściwe wydanie z ledgeru i price reference.

Wersje routing w source 2.6 liczą okresy assignment, także zmianę kanału.
Kontrakt inventory liczy rewizje w jednym dokładnym okresie. Adapter zachowuje
ID, okres, magazyn i availability oraz jawne `source_route_versions` z obiema
liczbami. Nie zmienia oryginalnych wymiarów i nie przenosi zwrotu do nowego
magazynu po zmianie mappingu.

## Zwroty i czas dostępności

Finansowe return events powstają dopiero dla rzeczywiście kupionej ilości,
według dotychczasowych okien kategorii/kanałów, oryginalnie zapłaconej ceny
i deterministycznego seeda. Obowiązuje limit wszystkich zwróconych sztuk
do faktycznej ilości zakupu.

Decyzja o refundzie jest odrębna od jakości towaru. W tej jawnej polityce
`wrong_size` i `changed_mind` mogą wrócić na stock; `damaged`, `defective`
i `not_as_described` mają quality rejected, nawet jeśli klient otrzymał refund.
Finansowo odrzucony zwrot nie restockuje. Każdy finansowy event ma dokładnie
jedną dyspozycję inventory i oryginalną fizyczną lokalizację sprzedaży.

Przyjęcie i sprawdzenie jakości mają własne opóźnienia ingestion/availability,
niezależne od późniejszej rejestracji refundu. Dyspozycja zapisuje osobno
`inventory_available_at` i `financial_available_at`. Ledger zachowuje causal
availability wcześniejszych ruchów; finansowy event zachowuje własny czas
i nie może być widoczny przed sprzedażą, której dotyczy.

Okno inventory obejmuje pełne doby danych popytu: od początku `start_date`
do wyłącznej północy po `end_date`. Zwroty w finansowym tailu są zachowane,
ale mają `outside_inventory_window` i nie produkują przyszłego restocku.
Ogon rozliczenia refundów nie jest dodatkowym okresem obserwacji popytu.
Także zaplanowane przyszłe receipts pozostają w oddzielnym simulation truth.

Panel, historyczne wersje observed quantity, ceny zrealizowane i kohorty
refundów są przeliczane z wykonanych sprzedaży. Read-only adapter przekazuje
builderom **causal availability**, zachowując surowe ingestion w zapisanych
sales. Późny fakt dodaje wersję obserwacji; wcześniejsza kohorta zawiera tylko
znane w jej cutoff sprzedaże i pozostaje niekompletna, jeśli inne jeszcze nie
były dostępne. Niedojrzały current panel daje `not_ready`, a nie `passed`.

## Bramka integracji

[Niezależny reconciler](../../data/inventory/source_reconciliation.py) sprawdza
bijekcję sale/item/price reference/issue, oryginalny koszyk, ceny znane w order,
refund i eligibility, dostawy oraz pełny panel lifecycle/calendar.
Na każdym ważnym dziennym grainie `observed + lost = latent` z niezmienionego
samplera. Facts nie zawierają latent demand, stockout flags ani parametrów truth.

Każdy snapshot na product/physical location/dobę UTC uzgadnia się z sumą ruchów
znanych w ostatniej mikrosekundzie doby. Sprawdzane są wszystkie grains,
quantity/reservations, unit, lineage i cutoff. Projekcja legacy zachowuje
jednorazowe opening i oryginalne source references. Nie ma niezależnego
losowania stock quantity ani automatycznego adjustment równoważącego błędy.

## Uruchomienie i dalszy odbiór

Z katalogu głównego repo:

```bash
services/api/.venv/bin/python -m data.inventory.run_source_commerce \
  --profile ai-smoke \
  --inventory-config data/tests/fixtures/source-inventory-config-v1.json \
  --output ci-cd/reports/data/source-inventory-candidate.json
```

CLI zwraca exit 0 dla `passed`, exit 1 dla `not_ready`/`failed`. Raport zawiera
prywatne arrivals/truth i nie jest wejściem API, loadera seeda ani feature workera.
`source-inventory-candidate-sha256-*` identyfikuje wykonanie; nie zastępuje
`source_dataset_id`, `snapshot_id` ani `curated_dataset_id`.
Fingerprint obejmuje generator, inventory runtime, kontrakty, worker i zależności.
[Odbiór lokalny](../evidence/ai/06/06.6a/README.md) wiąże wyniki z commitem.

[Typowane tabele 06.6b.1](inventory-source-tables.md) materializują ten wynik
i pełne projekcje 06.5, z oddzielnym facts/truth i uzgodnieniem po odczycie.
Następny zakres 06.6b.2 obejmuje integrację tabel z wersjonowanym domyślnym source,
manifesty/identity, lifecycle i kwalifikację coverage inventory, pełne source
quality/realism/readiness oraz nowy eksport/import/curated przez ścieżkę 03.
To także nowa publikacja projekcji i diagnostyki 06.5 przez ścieżkę 03.
Dopiero taki odbiór może zamknąć DATA-06. Zmieniony censoring wymaga nowej
oceny 04/05 i zgodnego feature schema przed wykorzystaniem prognoz przez 07/08;
dotychczasowe metryki modeli nie przenoszą się na nowy dataset.
