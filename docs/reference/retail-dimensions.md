# Wymiary handlowe profili AI

[Profile](data-profiles.md) · [Generowanie](../guides/data.md)

Profile `ai-*` mają dziewięć tabel wymiarów źródłowych; generator 0.6.0 ma także
[plany cen/promocji](retail-pricing.md) i [pełny panel popytu](daily-demand.md) oraz [chronologię/zwroty](retail-returns.md).
Ich kontrakt to `retail-dimensions-1.0.0`, opisany przez
[JSON Schema](../../data/contracts/retail_dimensions.v1.schema.json) i
[walidator](../../data/generator/dimension_quality.py). CSV ma komórki tekstowe;
walidacja dodatkowo sprawdza typy dat, UTC, klucze, relacje i reguły biznesowe.
Profile legacy `demo/small/medium/large` zachowują wcześniejszy zestaw i bajty CSV.
Nie są wejściem nowego kontraktu AI.

| Tabela | Znaczenie i klucz |
|---|---|
| `catalog_categories` | UUID kategorii, kod, department/segment i miesiące sezonu. |
| `product_catalog` | UUID produktu, unikalny SKU, niezależna marka, kategoria, lifecycle, jednostka i wielkość opakowania, syntetyczny unit cost w PLN i margin band. |
| `selling_locations` | Fizyczne miejsce sprzedaży: UUID, region, kraj, miasto, jurysdykcja kalendarza i strefy czasu. |
| `stock_locations` | Odrębny UUID fizycznego magazynu, region/kraj/miasto. |
| `channel_assignments` | Wersja ważnej pary selling location/channel; stabilny `legacy_store_id` dla adaptera. |
| `fulfillment_routes` | Wersja jawnego przypisania selling location/channel do stock location. |
| `assortment` | Wersja obecności produktu w danej parze selling location/channel, ograniczona lifecycle. |
| `business_calendar` | Jeden rekord na dzień UTC i ważną parę selling location/channel; flagi otwarcia, świąt i wydarzeń oraz granice doby. |
| `category_calendar` | Jeden rekord na dzień i kategorię; flaga sezonu kategorii. |

SKU używa polityki `sku-1.0.0`: `^[A-Z]{4}-[0-9]{6}$`.
Prefiks wynika z kategorii, np. `PETC` dla Pet Care. Marka jest wybierana osobno;
produkty tej samej kategorii mogą mieć różne marki. Koszt i margin band są
metadanymi symulacji, bez deklaracji rzeczywistej rentowności.

`--stores` dla profili AI oznacza liczbę **ważnych par lokalizacja/kanał**,
nie mnożnik wszystkich lokalizacji i kanałów. Domyślny `ai-smoke` ma trzy pary,
dwie fizyczne lokalizacje PL/DE i dwa magazyny. Ta sama lokalizacja może obsługiwać
więcej niż jeden kanał. `channel` ma wartości store/online/marketplace/wholesale,
a region jest atrybutem lokalizacji. Treningowa siatka nominalna liczy
days × products × valid pairs; lifecycle i asortyment zmniejszają liczbę aktywnych
kombinacji. Pełny panel obserwacji ma osobną politykę daily-demand-1.0.0.

## Okresy i adapter

Okresy assignments, routing i assortment są półotwarte:
`effective_from <= business_date < effective_to`. Ich wersje mają osobne UUID
oraz `available_at` w UTC. Nakładające się wersje są błędem; lookup z `as_of_time`
nie wybiera planu dostępnego później. W syntetycznym eksporcie wersje są znane
przed początkiem historii. Generator zmienia wersję w połowie historii;
przy jednym dniu powstaje jedna wersja.

`launch_date` jest włączne, `discontinue_date` wyłączne; pusty koniec oznacza brak
planowanego zakończenia. Status produktu opisuje stan na koniec eksportu.
Sprzedaż poza lifecycle/asortymentem albo w dniu zamknięcia jest odrzucana.

`products`, `stores` i `warehouses` są projekcjami kanonicznych tabel dla profili AI.
UUID produktu i magazynu pozostają identyczne w projekcji i źródle; store UUID
identyfikuje parę sprzedażową. Nie sprawdzaj unikalności UUID globalnie pomiędzy
master table i jej projekcją. Pola legacy symulacji pozostają do dalszej pracy etapu 02.

Routing nie zgaduje magazynu przy braku przypisania. Konfiguracja może zawierać
jawny routing do magazynu w drugim kraju. To plan fulfillment, bez uzgodnionego
ledgeru; stare stock movements nie są dowodem jego realizacji.

## Kalendarz i otwarcie

Polityka `pl-de-berlin-calendar-1.0.0` obsługuje lata **2024–2027**, Polskę oraz
**Berlin (DE-BE)**. Inny rok lub niemiecki land kończy się błędem i wymaga nowej
wersji polityki. Kalendarz jest zamrożony i nie pobiera świąt podczas generacji.
Źródła reguł:

- [Polskie dni wolne — tekst jednolity](https://api.sejm.gov.pl/eli/acts/DU/2025/296/text.pdf).
  Wigilia jest świętem od 2025 r.; [nowelizację ogłoszono 30.12.2024](https://dziennikustaw.gov.pl/DU/2024/1965).
- [Ustawowe święta Berlina](https://www.berlin.de/sen/inneres/buerger-und-staat/verfassungs-und-verwaltungsrecht/artikel.1435639.php).
- [Ustawa o jednorazowym 8.05.2025, ogłoszona 20.07.2024](https://www.berlin.de/sen/justiz/service/gesetze-und-verordnungen/2024/ausgabe-nr-28-vom-2072024-s-457-484.pdf).

`available_at` zmian świąt jest konserwatywnie ograniczone do dnia UTC po
ogłoszeniu: 2024-12-31 dla Wigilii i 2024-07-21 dla 8.05.2025.
To znany plan kalendarza, bez gwarancji kompletności sprzedaży.

Business date i business day bounds używają UTC (24 godziny).
Osobne local day bounds opisują Europe/Warsaw lub Europe/Berlin i mogą mieć
23/25 godzin przy zmianie DST; nie zmieniają grain sprzedaży na czas lokalny.
Testy obejmują obie strefy i obie zmiany DST w 2026 r.

Flagi obejmują weekend, święto, Easter Sunday, Christmas 24–26 grudnia,
Black Friday, Cyber Monday oraz sezon kategorii. `synthetic-opening-1.0.0`
otwiera store od poniedziałku do soboty poza świętami, wholesale od poniedziałku
do piątku poza świętami, a digital intake online/marketplace każdego dnia.
To jawna reguła syntetyczna: nie modeluje wyjątków niedziel handlowych ani godzin
otwarcia i nie jest oceną zgodności przedsiębiorstwa z prawem.

## Bramka źródłowa

Generowanie oraz odczyt manifestu 2.1/2.2/2.3 sprawdzają osiem hard gates:
schema/PK/SKU, rozdzielenie lokalizacji i kanałów, wersje/routing, katalog/lifecycle/
asortyment, pełny kalendarz ważnych par, sezon kategorii, zgodność adaptera
oraz sprzedaż w aktywnych i otwartych kombinacjach ze znanym routingiem.
Wynik trafia do `dimensions_report.json`, objętego checksumą manifestu.
Odczyt odtwarza wynik z CSV; ponowne obliczenie hashów błędnych tabel nie omija bramki.

Usunięcie obowiązkowego dnia kalendarza jest błędem, a nie zamknięciem albo zerem.
`active_daily_combinations` liczy ważne dni asortymentu przed ograniczeniem otwarcia.
Raport wymiarów nie certyfikuje panelu (observation_panel_status=not_ready);
coverage i statusy obserwacji potwierdza odrębna bramka [daily demand](daily-demand.md).
Readiness źródła i inventory pozostaje niegotowe; chronologia/zwroty
oraz pozostała izolacja simulation truth wymagają dalszych prac.
