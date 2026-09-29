# Snapshoty ledgeru i stockout truth AI 06.5

[Projekcja](../../data/inventory/projection.py) przetwarza wynik
[chronologicznego symulatora](chronological-inventory.md). Operacyjne snapshoty
są oddzielone od fizycznych sald i epizodów w `simulation_truth`.
[Odbiór](../evidence/ai/06/06.5/README.md) podaje kod i kontrole.
Domyślny source 2.6 nadal nie korzysta z tej ścieżki; `inventory_ready=false`.
[Typowane tabele 06.6b.1](inventory-source-tables.md) materializują te projekcje
na source profiles. Następny zakres 06.6b.2c to integracja domyślnego source
i nowa publikacja danych. [Kwalifikacja lifecycle/coverage06.6b.2b](inventory-label-qualification.md)
ma lokalny odbiór osobnych private windows z parent source ID.

## Snapshot i czas wiedzy

[Moduł snapshotów](../../data/inventory/snapshots.py) przyjmuje wyłącznie ledger
i konfigurację, bez dostępu do popytu lub supplier truth. Grain to fizyczny
produkt/stock location/business date. Kanały nie tworzą kopii wspólnego zapasu.
`on_hand` jest sumą ruchów biznesowych do cutoff dostępnych w `as_of_time`.
MVP ma `reserved_qty=0` i `available_qty=on_hand`; nie implementuje rezerwacji.
Nieznane opening daje `not_available` i null we wszystkich trzech ilościach.

Dobę UTC zamyka ostatnia mikrosekunda przed kolejną północą. Receipt o północy
należy do nowej doby. Częściowe pierwsza/ostatnia doba mają rzeczywiste
`period_from_at/to_at` i `is_full_business_day=false`; nie udają pełnego dnia.
`source_available_at`, liczba użytych ruchów i ostatni event dokumentują lineage.
Snapshot nie zawiera flag kompletności wyliczonych z przyszłych faktów.

`snapshot_at(..., snapshot_time=..., as_of_time=...)` umożliwia późniejszą
projekcję tego samego historycznego cutoff. Taka projekcja ma inne as-of i UUID;
odtworzenie pierwotnego as-of zachowuje wcześniejszy wynik.
Dzienne artefakty używają `snapshot_at=as_of_time` i nie uzupełniają braków
późniejszym stanem lub snapshotem innego warehouse.

Osobne fizyczne salda truth uzgadniają każdą dobę:

```text
closing = balance_before_period + opening_quantity + movement_delta
```

Opening występuje tylko w pierwszym okresie; następne snapshoty go nie dodają.
Bilans fizyczny może różnić się od historycznie znanego przy opóźnionej availability.
Nie jest alternatywną cechą do użycia w origin.

## Epizod i utracona sprzedaż

[Moduł truth](../../data/inventory/stockout.py) odtwarza fizyczny stan po każdym
ruchu. Epizod zaczyna się, gdy dostępny zapas wynosi zero, i kończy na pierwszym
ruchu przywracającym dodatni stan. Granice zawierają czas, sequence, event ID
i availability. Zero w opening jest left-censored: jego rzeczywisty początek
sprzed obserwacji jest nieznany. Brak recovery przed końcem jest right-censored,
z `end_at=null` i czasem obserwacji do wyłącznego końca okna.

Chwilowe zero pomiędzy zdarzeniami o tym samym timestampie pozostaje epizodem
o zerowym duration i różnych sequence. Nie ginie utracony arrival pomiędzy nimi.
Czas trwania jest całkowitą liczbą mikrosekund, bez zaokrąglenia do doby.

Każdy dodatni lost-sales outcome ma dokładnie jeden impact z episode ID,
produktem/warehouse, selling location/channel i demand ID. Arrival, który
wyczerpuje zapas i jest częściowo zrealizowany, należy już do początku epizodu.
Ilości są sumowane raz, bez pomnożenia przez kanały. Epizod może mieć zero lost
sales, jeśli nie było popytu; sama zerowa sprzedaż przy dodatnim stanie nie
tworzy epizodu. Nie określamy tu lifecycle/active-assortment eligibility —
integracja tych wymiarów pozostaje w 06.6 i kontrakcie modelu 08.

## Dojrzałe okna diagnostyczne

Dla dziennych origins powstaje prywatna diagnostyka nowych onsetów w
`(origin,origin+7 dni]`, bez feature datasetu, modelu ani publikacji label set.
Zero już w origin ma `already_stockout` i `incident_stockout=null`.
Brak znanego opening, niedostępne fakty o stanie w origin, niepełne okno
i niedojrzałe outcomes mają odrębne przyczyny `not_evaluable`.

Obserwacja kończy się wyłącznie w `end_at`: okno kończące się dokładnie tam
nie jest kompletne, bo zdarzenie na jego prawym końcu nie było obserwowane.
Pełne okno musi zmieścić się przed tym końcem. `label_available_at` uwzględnia
koniec siedmiu dni, jawne `truth_delay_seconds` oraz availability wszystkich
ruchów pozycji do końca okna. Recovery po oknie nie jest potrzebne do
potwierdzenia onsetu. Przed dojrzałością nie wystawiamy ani 0, ani 1.

To diagnostyka symulatora. Gotowy label/model 08 wymaga również poprawnych
lifecycle, coverage, feature lineage i oceny. Przy braku dojrzałych okien
lub obu klas raport zwraca `label_diagnostics_status=not_evaluable`.
Nawet przy obu klasach `model_ready=false`; nie wykonano odbioru AI 08.

## Kontrakt, uruchomienie i uzgodnienie

[Konfiguracja](../../data/contracts/inventory_projection_config.v1.schema.json)
wymaga wszystkich polityk, granic UTC, horyzontu 7 i opóźnienia truth.
[Schemat wyniku](../../data/contracts/inventory_projection.v1.schema.json)
`inventory-projection-1.0.0` rozdziela snapshoty i truth.
CLI weryfikuje hashes wejściowego wyniku 06.4, uzgadnia jego sprzedaż, zwroty,
dostawy i censoring, sprawdza zgodność okna, następnie projekcje każdego grainu.
Reconciliation odrzuca brakujące/zdublowane snapshoty, powtórzone opening,
fałszywe epizody, błędne recovery/duration, utracone impacts i niedojrzałe 0/1.

Najpierw uruchom [CLI symulatora](chronological-inventory.md), zapisując raport
pod `ci-cd/reports/data/ai06-04/simulation.json`. Następnie:

```bash
services/api/.venv/bin/python -m data.inventory.run_inventory_projection \
  --simulation ci-cd/reports/data/ai06-04/simulation.json \
  --config data/tests/fixtures/inventory-projection-config-v1.json \
  --evaluated-at 2026-07-11T00:00:00Z \
  --output ci-cd/reports/data/ai06-05/projection.json
```

`passed`/exit 0 potwierdza spójność artefaktu. `not_ready`/exit 1 zachowuje
nieznane snapshoty lub brakujące dane parent execution; `failed`/exit 1 oznacza
błąd kontraktu, integralności lub procesu. Sam `not_evaluable` diagnostyki modelu
nie jest uszkodzeniem poprawnej projekcji. Pełny raport zawiera private truth,
nie jest eksportem API/cech. DATA-06 i nowa publikacja source/curated pozostają otwarte.
