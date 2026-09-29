# Kwalifikacja lifecycle i coverage inventory — AI 06.6b.2b

Kwalifikacja daje prywatne okna stockout w grainie
**product × stock location × origin**. Jest osobnym, niezmiennym artefaktem
`inventory-labels-sha256-*`, wskazującym zweryfikowany `source-sha256-*` 2.7.
Nie dopisuje tabel ani statusów do odebranych źródeł i nie zmienia kontraktu
27 native tables. [Schema](../../data/contracts/inventory_label_qualification.v1.schema.json)
ma wersję `inventory-label-qualification-1.0.0`, policy
`active-physical-window-1.0.0`. [Odbiór](../evidence/ai/06/06.6b.2b/README.md)
dotyczy kwalifikacji źródła; model 08 i jego temporal splits mają osobny odbiór.

## Reguła okna

Origin to ostatnia mikrosekunda doby UTC ze snapshotu 06.5. Label oznacza
**nowy fizyczny epizod stockout w `(origin, origin + 7 dni]`** przy dodatnim,
znanym zapasie w origin. Fizyczny proces i dostępność ledgeru są uzgodnione
przez czytnik source 2.7 i projekcje 06.5 przed kwalifikacją.

1. Produkt musi być po launch i przed discontinue. Pole bieżącego `status`
   nie zastępuje historycznych dat lifecycle. Catalog, assignment, assortment
   i route muszą być dostępne w origin; nie używamy obecnego warehouse.
2. Co najmniej jedna aktywna para selling location/channel musi historycznie
   kierować produkt do tej fizycznej stock location. Kilka kanałów współdzieli
   jedną pozycję i jeden label. Zamknięty sklep nadal może mieć aktywny asortyment.
3. Nieznany ledger lub ruch z przeszłości niedostępny w origin oznacza
   `not_evaluable`. Zero w aktywnym origin oznacza `already_stockout`, bez
   labelu incident. Nieaktywny produkt lub nieużywana pozycja są wykluczone
   przed tą regułą; nie stają się przykładami stockout.
4. Pełne okno musi mieścić się przed końcem obserwacji. W każdej z kolejnych
   siedmiu dób sprawdzamy historyczny lifecycle, assignment, assortment,
   route i kalendarz. Availability wymiarów sprawdzamy na początku tej doby;
   późno opublikowany mapping nie kwalifikuje jej retrospektywnie.
5. Osobny inventory stream certificate tej samej pozycji musi obejmować
   cały prefix od opening do **chwili późniejszej niż** koniec okna.
   Wybieramy najwcześniej dostępny spełniający certificate. Kompletny panel
   sprzedaży i certificate innego warehouse nie zastępują coverage ledgeru.
6. Każda aktywna, skierowana do tej pozycji para kanał/lokalizacja musi mieć
   pełną, poprawną obserwację dzienną: positive, zero lub closed, zgodną
   z kalendarzem. Incomplete lub brakujący wiersz pozostawia pusty label.
7. Dostępność labelu to maksimum availability fizycznych outcomes, inventory
   certificate, wszystkich wymaganych obserwacji i końca pełnych dób.
   Label 0/1 powstaje dopiero po tej chwili. Przyszły receipt poza oknem,
   plan dostawy lub financial return tail nie rozszerza coverage ani maturity.

Brak route dla aktywnej pary ma nieznane fizyczne przeznaczenie: konserwatywnie
wykluczamy dotkniętą dobę dla wszystkich stock positions produktu.
Zmiana route może zachować aktywność starego magazynu przez inne kanały;
nie przenosimy labelu ani lineage do nowego magazynu.
Brak popytu przy dodatnim zapasie i pełnym aktywnym oknie może dać label 0.
Sam brak transakcji ani zero sprzedaży nie daje labelu 1.

## Wynik i gotowość

| Status wiersza | Znaczenie labelu |
|---|---|
| `evaluable` | `incident_stockout` ma 0 albo 1; okno przeszło eligibility, coverage i maturity. |
| `already_stockout` | Zero w aktywnym, znanym origin; label incident jest null. |
| `not_evaluable` | Label null i jawny reason: lifecycle, assortment, route/availability, calendar, inventory, coverage lub tail. |

Każdy wiersz zapisuje origin/window route IDs, inventory coverage ID, liczbę
pełnych sales days i availability labelu. Raport rozdziela liczby klas,
statusy i powody wykluczeń. `label_qualification=qualified` wymaga
`source_facts_ready=true` oraz obu klas w kwalifikujących się oknach.
Brak klas lub niegotowe źródło daje `not_evaluable`.
To kwalifikacja **źródłowych okien**, bez potwierdzenia train/validation/test,
kalibracji, zgodnych forecastów czy przydatności produkcyjnej danych.
`source_ready`, `inventory_ready` i `model_ready` pozostają false.

Raw report source 2.7 zachowuje historyczne `label_qualification=not_evaluated`.
Aktualną kwalifikację odczytujemy z tego osobnego artefaktu, z właściwym parent ID.
Nowy handoff 03 musi przenieść go jawnie jako evaluation truth z własnym
kontraktem i lineage; nie wolno dołączać go do worker features.

## Uruchomienie i kontrola

Po wygenerowaniu [source 2.7](inventory-source-dataset.md), z głównego katalogu:

```bash
services/api/.venv/bin/python -m data.inventory.run_qualification \
  --source ci-cd/reports/data/inventory-source-27/source-sha256-<ID> \
  --output-root ci-cd/reports/data/inventory-labels \
  --output ci-cd/reports/data/inventory-labels-receipt.json
```

CLI exit 0 oznacza poprawnie zapisany i ponownie zweryfikowany artefakt.
Gotowość klas jest osobnym polem raportu i może mieć `not_evaluable`.
Exit 1 oznacza naruszenie kontraktu/integralności, bez zaakceptowanej publikacji.

Katalog zawiera manifest, raport oraz
`simulation_truth/inventory_qualified_windows.json`. ID wiąże parent source,
policy/schema, grain/horizon/evaluation, logical hashes wyników i fingerprints
kodu/zależności. Lokalne ścieżki i timestamp wykonania nie zmieniają ID.
[Czytnik](../../data/inventory/qualification_io.py) ponownie weryfikuje wszystkie
58 tabel parent source i jego 36 gates, wylicza wszystkie okna i raport,
porównuje pełne canonical bytes i descriptor oraz sprawdza checksums,
placement i file allowlist. Zmiana labelu i ponowne przeliczenie ID/checksum
nie omija uzgodnienia. Reuse nie naprawia uszkodzonych artefaktów.

Odbiór obu standardowych profili dwukrotnie, wraz z controlled configs:

```bash
services/api/.venv/bin/python -m scripts.data.verify_ai06_qualification \
  --output ci-cd/reports/data/ai06-06b2b/acceptance.json
```

Budżet 300 s / 1024 MiB obejmuje świeży generator, source CSV, gates/readback
i kwalifikację/readback. [Snapshot/import06.6b.2c.1](inventory-snapshots.md) mają
[lokalny odbiór](../evidence/ai/06/06.6b.2c.1/README.md). Curated, pełny pipeline
i przełączenie domyślnego źródła pozostają zakresem 06.6b.2c.2. Następnie potrzebne
są zgodne oceny04/05 na nowych IDs; DATA-06 i model 08 pozostają otwarte.
