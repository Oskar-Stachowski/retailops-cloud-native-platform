# Odbiór źródła i izolacja cech AI

Źródło **2.6.0**, generator **0.8.0**, kanonizacja **1.6.0**.
Profile AI eksportują 40 CSV; demo/small/medium/large zachowują 17 tabel
i wcześniejsze bajty CSV. [Odbiór DATA-05](../evidence/ai/02/data05/README.md)
kwalifikuje ograniczone profile do rozpoczęcia AI 03.

## Fakty, symulacja i wyniki operacyjne

`products` i `stores` w AI zawierają wyłącznie fakty. Parametry popytu,
elastyczność, sezonowość i return rate są w `product_simulation_parameters`;
traffic multiplier i promo sensitivity — w `store_simulation_parameters`.
[Schema](../../data/contracts/retail_simulation.v1.schema.json) oraz
[walidator](../../data/generator/simulation.py) egzekwują
`retail-simulation-parameters-1.0.0`, wartości i pełne, jednoznaczne pokrycie encji.

W AI `sales` nie ma dawnych kolumn latent demand, stockout, uplift, elasticity
effect ani noise. Ich puste historyczne nagłówki pozostają czytelne w eksportach
2.0–2.4. `daily_demand_truth`, `promotion_effect_truth` i obie tabele parametrów
mają klasę `simulation_truth`. Demonstracyjne forecasts/anomalies/alerts są
`source_operational_output`; nie są labelami nowego AI. Legacy inventory nie
jest kwalifikowane do modeli.

Pełny eksport CSV pozostaje płaski. Fizyczny layout facts/evaluation_truth,
Parquet, niezmienne snapshoty i importer są zakresem [AI 03](../plans/ai/etapy/03-snapshot-curated.md).
Izolację obecnego workera zapewnia osobny proces z własnym systemem plików.

## Granica procesu

[Właściciel źródła](../../data/generator/feature_admission.py) weryfikuje pełny
manifest, checksumy i bramki, po czym publikuje cztery wąskie projekcje:

| Wejście workera | Dopuszczona informacja |
|---|---|
| daily_demand_observations | ID, dzień, product/location/channel, observed units/status, availability i trzy flagi aktywności/otwarcia/kompletności |
| daily_demand_versions | ID obserwacji i wersji, ten sam grain, numer wersji, ilość/status oraz availability; bez revenue, wyceny i parametrów symulacji |
| product_catalog | id, category_id, brand |
| catalog_categories | id, name |

[Allowlista](../../ml/features/fact_input.py) `forecast-facts-2.0.0` odrzuca
każdą dodatkową tabelę lub kolumnę, także koszt, revenue, realized price,
inventory i truth. Worker sam ponownie sprawdza wejście i semantykę cech 3.1.
Przekazanie pełnych tabel do dawnego buildera AI kończy się błędem.
Admission sprawdza również checksumy i canonical hashes faktycznie projektowanych
rekordów; podmiana pliku po pierwszej walidacji nie dostaje starego parent ID.

[Runtime](../../ml/features/isolated_runtime.py) `facts-docker-runtime-1.0.0`
uruchamia [worker](../../ml/features/worker.py) z obrazu Python 3.11.15
przypiętego digestem. Montuje wyłącznie siedem jawnych plików kodu bez generatora.
Fakty płyną przez stdin, wynik przez stdout; katalog danych i repo nie są montowane.
Kontener ma read-only root/mount, user 65534, brak sieci, capabilities i nowych
uprawnień oraz limity 256 MiB, jednego CPU i 64 procesów. Nie dostaje socketu
Dockera ani zmiennych środowiska hosta. Brak Dockera/obrazu przerywa wykonanie;
nie ma automatycznego uruchomienia na hoście.

Supervisor pozostaje zaufanym właścicielem danych: waliduje source i zapisuje
wynik oraz lineage. Izolowana granica obejmuje proces obliczający cechy/runtime.
To lokalny odbiór tej ścieżki, bez deklaracji wdrożenia przyszłego serving AI.
Kod istniejącego API nie importuje generatora ani tych tabel; demo i obecny RF
pozostają osobnymi ścieżkami legacy.

## Bramki i interpretacja raportów

`source_report.json/md` agreguje **46 hard checks**: 15 strukturalnych, osiem
wymiarów, sześć cen, sześć popytu, siedem zwrotów oraz trzy kontroli schema,
parametrów i projekcji faktów oraz historię wersji obserwacji. Każdy check ma wersję polityki, use case,
sample size, value, threshold, status i evidence. Wymagany błąd blokuje eksport
i admission. Odczyt 2.6 przelicza raporty źródła, jakości i realizmu z CSV;
zmiana samych checksumów nie pozwala podstawić fałszywego wyniku.

`realism_report.json/md`, polityka `observed-sales-realism-1.1.0`, podaje
udział top 20% całego katalogu (także produktów bez sprzedaży), średnią liczbę
różnych pozycji koszyka oraz zero-sales i final refunded unit rate według
demand bucket/kategorii/kanału. Mianownik zer wyklucza zamknięte dni.
Top 20% katalogu to ceil(0,2 × liczba produktów), z produktami bez sprzedaży.
Progi diagnostyczne z kontraktu: revenue share 45–80%, koszyk 1,2–3,5 pozycji.
Katalog poniżej 50 produktów i segment/koszyk poniżej 30 obserwacji mają
`not_evaluable`; odchylenia większych próbek mają `warning`.
Przyczynowy uplift i stockout są `not_ready`, z wartością null.
Porównanie średniej promowanej sprzedaży nie dowodzi efektu przyczynowego.
Refund rate wykorzystuje dojrzały ogon, nie przepisuje historycznych labeli/net.
Raport diagnostyczny nie certyfikuje rynku ani dużych profili treningowych.

| Zastosowanie | Bieżący status |
|---|---|
| Źródło observed_sales_units do AI 03 | source_ready=true po wszystkich hard gates profilu AI |
| Forecasting/model serving | not_ready; snapshot/curated i ocena AI 03–05 |
| Anomaly, stockout, replay | not_ready; cross-repo import/replay, ocena modeli i ledger mają własne bramki |
| Inventory | inventory_ready=false; cechy zapasu są pominięte |
| RAG | not_applicable dla odbioru sprzedaży |

Polecenia są w [instrukcji danych](../guides/data.md). Cechy mają transformację
`daily-demand-history-worker-1.0.0`, pełny source parent i fingerprint kodu runtime.
Historyczne [eksporty 2.0–2.5](source-compatibility-fixtures.md) zachowują IDs.

Wersje obserwacji są append-only: nowa sprzedaż lub korekta dopisuje stan z
późniejszym `available_at`. Worker przekazuje historię w cechach; odczyt dla
origin wybiera ostatnią znaną wersję i nie ujawnia późniejszego prefiksu.
Brak wymaganej historii ma status `missing_history`, nigdy losowe zero.
[Kontrakt historii](daily-demand.md#historia-obserwacji) opisuje walidację.
Fingerprint źródła i cech obejmuje wszystkie siedem wykonywanych plików workera,
w tym inicjalizatory pakietów. Zmiana dowolnego pliku zmienia hash kodu i ID
również przy identycznych wierszach; zmieniony kod ma provenance `modified`.
Dawne manifesty zachowują własne schematy, provenance i IDs; nie otrzymują
wymyślonej historii korekt. Nowy admission wymaga źródła 2.6 i cech 3.1.
