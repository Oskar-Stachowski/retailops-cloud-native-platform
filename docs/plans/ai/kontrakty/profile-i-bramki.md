# Profile, budżety i bramki odbioru

**Status: konfiguracja, identity, wymiary, kalendarz, ceny/promocje, popyt/panel/koszyki oraz chronologia/zwroty mają lokalny odbiór;
pełne źródło ma lokalny odbiór, bramki modeli pozostają planem.**
[Konfiguracja 1.0.0](../../../../data/generator/configuration.py) jest wykonywalnym źródłem
rozmiarów i dat. Profile AI mają [kanoniczne wymiary](../../../reference/retail-dimensions.md),
stock locations, ważne pary i osiem hard gates wymiarów oraz
[znane plany cen/promocji](../../../reference/retail-pricing.md) i sześć bramek cenowych.
[Odbiór DATA-04](../../../evidence/ai/02/data04/README.md) potwierdza coverage cen
i uzgodnienie transakcji. [Popyt/panel/koszyki](../../../evidence/ai/02/demand-panel/README.md)
mają pełny ważny panel, cechy 3.0 i sześć bramek demand. Obserwacje cen są sparse;
generator zachowuje CSV, a [03.1](../../../reference/parquet-artifacts.md) dodaje
konwersję 40 tabel do typed Parquet. [DATA-03](../../../evidence/ai/02/data03/README.md)
ma siedem bramek chronologii/zwrotów, dwa cutoffy i 39-dniowy ogon.
[DATA-05](../../../evidence/ai/02/data05/README.md) kwalifikuje source 2.6:
46 hard gates, rozdzielone parametry i izolowany worker z czterema projekcjami faktów oraz historią obserwacji as-of.
Chunked Parquet i niezmienny exporter mają lokalny odbiór 03.1/03.2.
[Snapshot 03.2](../../../reference/ai-snapshots.md) przelicza bramki źródła
i dopuszcza wyłącznie gotowe wymagane use cases. Handoff/import/curated mają
[lokalny odbiór 03.3–03.5](../../../evidence/ai/03/03.5/README.md);
pełna bramka cross-repo, Required CI i dalsze bramki modeli pozostają otwarte.
Wartości są założeniami dla tego projektu syntetycznego, nie dowodem realizmu rynku.
Zmiana polityki wymaga jawnego diffu i nowej wersji, przed oglądaniem final testu.

## 1. Jeden zestaw profili

| Profil | Dni | Produkty | Aktywne pary selling location/channel | Stock locations | Górna liczba daily rows przed lifecycle | Cel |
|---|---:|---:|---:|---:|---:|---|
| `demo` | Dotychczasowy kontrakt | Dotychczasowe | Dotychczasowe | Dotychczasowe | Dotychczasowa | API/UI compatibility, CSV |
| `ai-smoke` | 30 | 20 | 3 | 2 | 1 800 | Schema, import, kontrakty i mały replay; nie pełne backtesting |
| `ai-temporal-smoke` | 102 | 8 | 3 | 2 | 2 448 | 28 warmup + 60 dni originów + 14 label tail; wykonanie całej ścieżki czasowej |
| `ai-dev` | 365 | 100 | 5 | 3 | 182 500 | Lokalny rozwój modeli, Parquet |
| `ai-training` | 730 | 200 | 10 | 4 | 1 460 000 | Końcowa ewaluacja portfolio, partycjonowany Parquet |
| `ai-load` | Jawna konfiguracja | Jawna | Jawna | Jawna | Limit deklarowany przed startem | Opcjonalny performance/streaming/S3; po podstawowym portfolio |

Wiersze są iloczynem dni, produktów i poprawnych aktywnych par, nie liczbą losowych transakcji. Lifecycle, okresy asortymentowe i assignmenty mogą zmniejszyć liczbę; generator wylicza dokładny expected count. Liczbę orders/items/events oszacować oddzielnie przed generacją, z limitem pozwalającym bezpiecznie przerwać duży run.

Domyślny powtarzalny koniec profili AI to `2026-07-31`; start wylicza się jako `end_date - (history_days - 1)` dni. CLI przyjmuje jawną inną datę i zapisuje ją w effective config. Nie używa niejawnie daty „dzisiaj”. Demo zachowuje istniejącą datę. Profile small/medium/large pozostają kompatybilne, ale nie zastępują profili AI w evidence.

W `ai-temporal-smoke` 60 dni originów dzieli się czasowo w wersjonowanym split config; test dojrzałości horyzontów używa 14 dodatkowych dni. Nie oznacza to 60 poprawnych predykcji dla każdej nowo uruchomionej serii — cold start jest jawny. Smoke dowodzi wykonania kontraktów; nie uprawnia do ogłoszenia przewagi modelu.

Development używa seed 42. Końcowa robustness policy obejmuje wcześniej zamrożone seedy `[42, 137, 2026]` oraz scenariusze normal/promotion/demand shock/inventory constraint. Raportuje się wyniki każdego seeda/scenariusza i agregat. Nie wybierać seeda po wynikach testu. Development tuning prowadzi się na wcześniejszych oknach; późniejsze holdouty wszystkich seedów pozostają nietknięte do finalnej oceny.

## 2. Budżet wykonania i plików

- Standardowe Data CI uruchamia oba smoke dwukrotnie przez `make data-parquet-check`.
  Polityka `ai03-snapshot-budget-1.0.0` wymusza 5 minut i 1 GiB peak RSS na każdy
  kompletny profil: generacja/kwalifikacja/export/verify/reexport, bez instalacji
  zależności. [Benchmark 03.2](../../../evidence/ai/03/03.2/README.md)
  potwierdza lokalny zapas; zdalny wynik wymaga uruchomienia CI nowego brancha.
- Maksymalny śledzony fixture: 5 MiB po rozpakowaniu; co najwyżej jeden bieżący `ai-smoke`, bez pełnego training export. Małe archiwa wcześniejszych wersji służą wyłącznie regresji odczytu i łącznie mieszczą się w tym limicie, zgodnie z [polityką plików](dane-i-czas.md). Bieżące smoke i temporal smoke są generowane w temp. Ciężkie seedy/scenariusze są lokalne/manualne lub w osobnym jobie.
- `ai-dev` i `ai-training` zapisuje się chunkami. Raport mierzy czas, peak memory, rows/s oraz bytes. Jeżeli pełny profil przekracza zasoby, poprawić zapis/przetwarzanie lub jawnie stworzyć nowy mniejszy profil; nie nazywać go dotychczasowym `ai-training`.
- Koszt zależności, pobierania obrazów, treningu TensorFlow i calls do Bedrock raportować oddzielnie; smoke dataset nie jest budżetem całej platformy.

## 3. Statusy i zachowanie CLI

Każdy check zapisuje `check_id`, policy version, use case, severity, status, value, threshold, sample size, opis oraz ścieżkę evidence. Dozwolone statusy: `passed`, `warning`, `failed`, `not_ready`, `not_evaluable`, `not_applicable`.

`failed` dla hard gate oraz `not_ready/not_evaluable` dla wymaganej bramki use case’u powodują niezerowy exit code i blokują promocję/publikację danego wariantu. `warning` nie blokuje automatycznie, ale wymaga jawnego uzasadnienia w karcie. `not_applicable` jest dopuszczalne tylko dla możliwości wyłączonej w danym wariancie, np. inventory przed etapem 06; nie udaje wyniku passed.

Manifest ma readiness osobno dla `forecasting`, `anomaly`, `stockout`, `replay` i `rag`. Etap 03 może opublikować snapshot forecast-only z `inventory_ready=false`, `stockout=not_ready`, `anomaly=not_ready`. Globalny status „wszystko ML-ready” jest wtedy zakazany.

## 4. Bramki twarde

| Warstwa | Warunek odbioru |
|---|---|
| Wszystkie dane | Poprawne schematy/typy/wersje/enums, wymagane kolumny; 0 złamanych PK/FK i niedozwolonych null |
| Handel | 0 nieuzgodnionych order totals, items/sales/returns; suma zwrotów ≤ zakup; poprawna waluta i precyzja |
| Chronologia | 0 przypadków sold przed ordered lub returned przed sold; jawne watermarki/tail; poprawne okresy i availability |
| Cena/promocja | 100% coverage ważnych kombinacji, brak sprzecznych nakładających się cen; transakcje zgodne z kalendarzem |
| Panel | 100% ważnej siatki, jawne zera vs missing/closed; lags według dat, nie kolejności sparse rows |
| Point-in-time | 0 future source/target-day covariates/nieprawidłowych wersji; test historycznej niezmienności po late correction |
| Truth separation | 0 simulation-only fields w features oraz brak runtime access do truth |
| Identity | Checksums zweryfikowane; identyczny input powtarzalny; różny rozmiar/seed/treść nie kolidują; brak nadpisania |
| Inventory od 06 | 100% ledger reconciliation i poprawnych mappings; 0 nieuzasadnionych ujemnych stanów; wspólna pula bez podwójnego liczenia |
| Labels | Okna dojrzałe, brak overlap leakage; brakujące/censored outcomes nie są negatywami |
| Replay od 07/10 | Wszystkie injekcje mają rozliczone expected actions; powtórny replay bez drugiego skutku; brak ACK bez durability w transporcie10 |

Każda ważna bramka ma fixture pozytywny i celowo błędny. Istniejących 15 checks nie usuwać; rozszerzyć je o wykryte luki. Sama liczba zielonych checks nie jest dowodem gotowości.

## 5. Realizm i liczebność

Początkowe zakresy `ai-training`: top 20% produktów daje 45–80% revenue; średnio 1,2–3,5 pozycji w koszyku; po 06 stockout rate 2–12%; DQ injections 0,5–4% raw events; business anomaly prevalence 0,3–2% ważnych obserwacji. Definicje mianowników i jednostek muszą być w konfiguracji. To początkowe zakresy warning/realism, chyba że przed final testem konkretna decyzja zamieni je w hard gate. Nie zwiększać zakresów po zobaczeniu wyniku testowego.

Zero-sales rate i return rate raportuje się według demand bucket/kategorii/kanału; nie ma jednej uniwersalnej wartości. Brak zera w całym AI dataset, niezamierzona stała cecha, dokładne category↔brand albo region↔channel mapping wymagają naprawy lub konkretnego uzasadnienia. W smoke, z małym sample size, wskaźniki realizmu mogą być `not_evaluable`; kontrakty strukturalne nadal są wymagane.

Każdy wymagany typ anomalii/scenariusz ma pozytywne epizody i czyste kontrolne okna. Raport podaje ich liczby, czas trwania i overlap. Bez pozytywów recall/PR-AUC jest `not_evaluable`, bez predykcji dodatnich precision także nie może automatycznie dać „idealnego” wyniku. Dla stockout wymagane są obie klasy i wystarczająca liczebność segmentu do ustalonej przed testem polityki. Jeśli próba jest za mała, raportować ograniczenie, łączyć wcześniej zdefiniowane segmenty albo generować większy profil; nie ukrywać go jako passed.

## 6. Bramki modeli i etapów

Metryki, konfiguracja progów, definicja segmentów, split i capacity są zamrożone przed final testem. Wartości progów biznesowych wybiera się na development/validation, zapisując powód; nie obiecuje się konkretnego polepszenia bez pomiaru.

- Forecast: te same originy/targety i polityka historii dla baseline/candidate; MAE, WAPE, bias, segmenty/horyzonty, intervals/coverage i koszt. Gdy suma actual wynosi 0, WAPE=`null/not_evaluable`, a dodatnia błędna prognoza nadal zwiększa MAE i zero-series overforecast. MAPE tylko na `y>0` z podaną coverage.
- Anomaly: observation-level precision/recall i false alerts/1000 oraz episode-level detection/delay; przed testem ustalona tolerancja i deduplikacja alertów. DQ errors i business anomalies raportować oddzielnie.
- Stockout: PR-AUC, Brier, calibration/reliability, recall@capacity, porównanie do LR; censored i already-stockout osobno. OOF forecast i pełne lineage obowiązkowe.
- TensorFlow: te same dane i evaluation gates; challenger nie musi wygrać. Negatywny wynik z rzetelnym kosztem jest poprawnym rezultatem portfolio.
- Finalny odbiór: wszystkie use cases, integracja i wymagania platformy mają rzeczywiste evidence właściwe dla etapu; flagi readiness nie są dopisywane ręcznie zamiast uruchomienia kontroli.
