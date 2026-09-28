# Dzienny popyt, panel i koszyki AI

[Profile](data-profiles.md) · [Wymiary](retail-dimensions.md) · [Ceny](retail-pricing.md)

Profile ai-* używają daily-demand-1.0.0, generatora 0.7.0 i source schema 2.5.0.
Trzy tabele popytu, trzy [zwrotów](retail-returns.md) i dwie parametrów
symulacji dają łącznie **39 CSV**. Demo i legacy zachowują wcześniejsze
reguły oraz bajty danych. [JSON Schema](../../data/contracts/retail_demand.v1.schema.json)
opisuje komórki CSV; [walidator](../../data/generator/demand_quality.py) sprawdza semantykę.

| Tabela | Znaczenie |
|---|---|
| daily_demand_observations | Wszystkie ważne dni product/selling location/channel; units, liczba różnych zamówień, gross revenue, realized price, promocje, availability i kompletność. |
| daily_demand_exclusions | Nieaktywne kombinacje nominalnej siatki; reason lifecycle/assignment/assortment, poza mianownikiem ważnego panelu. |
| daily_demand_truth | Składniki formuły, expected rate, rounding draw i latent units otwartych ważnych dni; klasa simulation_truth. |

Grain to business_date/product_id/selling_location_id/channel. Nominalna siatka
liczy dni × produkty × ważne pary, bez mnożenia dowolnych kanałów. Lifecycle,
assignment i assortment mają wersję znaną na początku dnia. Brak kalendarza
powoduje błąd, nigdy zero.

## Jedna formuła przed koszykiem

`expected_rate = base_rate × product_factor × location_factor × weekly_factor × seasonal_factor × lifecycle_factor × price_factor × promotion_factor × anomaly_factor × noise`.

Product factor to demand_weight użyty **dokładnie raz**; legacy normal_daily_sales
nie zasila formuły. Base rate: hero 8, core 5,6, seasonal 3,2, new 1,8,
declining 1,5, clearance 1,2, long tail 0,6. Location factor to traffic_multiplier.
Weekend ma 1,2; holiday_peak listopad/grudzień 1,4; spring_summer_peak
kwiecień–sierpień 1,2; pozostałe 1. Chronologiczny lifecycle progress:
new 0,45 + 1,25 × progress; declining 1,30 − 0,65 × progress;
clearance 0,75 + 0,55 × progress; pozostałe 1. Anomaly factor jest 1.
Nowa ścieżka nie dodaje injekcji anomalii/DQ.

Price/promotion factor używają znanych planów z DATA-04 na początku dnia.
Początkowa globalna cena price_plans jest referencją elastyczności także po
odczycie CSV. Noise jest uniform 0,78–1,24. Ilość to floor(rate) plus
Bernoulli(frac(rate)), według osobnego uniform draw; może wynosić zero.
RNG ma klucz seed/dzień/produkt/lokalizacja/kanał, niezależny od koszyka.
To syntetyczna polityka, bez deklaracji kalibracji do rynku.

Przed ledgerem nie ma inventory cap: próbka jest ilością generowanej sprzedaży
dnia. Nie dowodzi niezaspokojonego popytu ani wiarygodnego stockout. Składniki
i próbka są w daily truth; AI sales nie zawiera nagłówków latent/noise/stockout.
Parametry produktów/stores mają [osobne tabele symulacji](source-acceptance.md).

## Koszyki zachowują dzienne ilości

Najpierw powstaje budżet sztuk dnia i pary. Anchor jest losowany proporcjonalnie
do pozostałych sztuk. Komplementarne aktywne SKU z dodatnim budżetem są losowane
bez replacement, pozostałe SKU uzupełniają koszyk także bez replacement.
Fashion/Beauty i Grocery/Pet Care są komplementarne; pozostałe preferują własną
kategorię. Nie wybiera się stale pierwszych produktów katalogu.

Online/store/marketplace mają 1–3 linie, wholesale 2–4, do liczby dostępnych SKU.
Ilość linii to 1–3 sztuki (wholesale 1–6), do pozostałego budżetu. Koszyk nie
dodaje popytu. Wszystkie sztuki są przydzielone raz; wycena używa rzeczywistej
ilości także dla bundle. Order/items/sales i dzienne agregaty sztuk/przychodu
są uzgodnione. Ordered/sold mają rosnący czas w obrębie dnia; pełne bramki
chronologii oraz okna/tail zwrotów egzekwuje [DATA-03](retail-returns.md).

## Zero, zamknięcie i brak danych

| Status | Units / revenue | Kompletność i użycie |
|---|---|---|
| observed_positive | Dodatnie units i rzeczywisty gross revenue | Otwarty ważny dzień, kompletne źródło. |
| observed_zero | 0 / 0,00 | Otwarty ważny dzień po zakończeniu okna; bez fikcyjnej transakcji quantity=0. |
| closed | 0 / 0,00 | Ważny asortyment, zamknięta para; odrębny status, pomijany przez lookup historii. |
| missing | Puste wartości, null label cech | source_data_complete=false; nie staje się zerem, blokuje kompletny eksport. |
| inactive | Brak w ważnym panelu | Osobna tabela wykluczeń, poza coverage denominator. |

Availability pełnego dnia to maksimum następnej północy UTC i czasów
ingestii/wyceny faktów. Zerowy dzień staje się znany po zamknięciu okna.
Manifest ma osobny syntetyczny watermark daily observations na północ po końcu
historii; dane dostępne później blokują kompletny eksport. Legacy strumienie
zachowują brak gwarancji kompletności. Return units i net revenue opisują wiedzę
przy day close; dojrzałość okien oraz późniejsze refundacje opisują
[rozliczenia zwrotów](retail-returns.md) z własnymi cutoffami. Nie zmieniają targetu sprzedaży.

## Cechy, bramki i dalsza praca

[Cechy AI 3.0](ml-features.md) zachowują pełny fizyczny grain i statusy panelu,
bez inventory, truth i realized price/revenue target day. Calendar lag sprawdza
dokładną datę względem origin i availability; luka, missing/closed lub późny
rekord dają unknown. Nie przesuwa sparse wierszy.

Sześć hard gates sprawdza schema, dokładną siatkę/wykluczenia, agregaty/statusy,
koszyki, formułę/budżet i kompletność. Generacja, feature builder i odczyt v2
odtwarzają kontrole; demand_report JSON/MD są objęte checksumami. Przeliczenie
hashów nie ukrywa luki ani fałszywego raportu. Raporty wymiarów/pricing potwierdzają
własne komponenty; ich wcześniejsze flagi panelu nie zastępują bramki demand.
Kanonizacja 1.5.0 i demand policy wchodzą do source identity.

Source 2.0–2.4 i features 2.0/3.0 zachowują IDs i parent.
[Odbiór źródła](source-acceptance.md) kwalifikuje AI do snapshotu 03;
inventory i modele pozostają not_ready.
Forecast na cechach 3.0 jest etapem AI 04.
