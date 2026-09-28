# AI 00 — audyt stanu wyjściowego

**27.09.2026: można rozpocząć [etap 01](../../../plans/ai/etapy/01-fundament-projektu.md).**
Audyt ma komplet wymaganych pomiarów i [backlog z kryteriami odbioru](../../../plans/ai/backlog.md).
Obecne dane nie spełniają jeszcze kontraktu źródła AI 02 ani importu AI 03.
Nie jest to dopuszczenie modeli do serving, integracji strumieniowej ani wdrożenia AWS.

## Rewizja i sposób sprawdzenia

- Źródło: `cbf28b2a66e7e5f205cf73d9bfe620c491e22d93`, branch `ai/implementation`,
  czysty worktree przed audytem. Nie znaleziono `AGENTS.md` w repo ani katalogach nadrzędnych.
- Pomiary lokalne: 2026-09-27 UTC, macOS 26.6.2 arm64, CPython 3.11.15.
  Generator, API i 138 testów użyły lokalnego venv API: scikit-learn 1.5.2,
  joblib 1.4.2, NumPy 2.4.4, SciPy 1.17.1, pytest 9.0.3.
  Odczyt zachowanych modeli użył osobnego venv treningu ze scikit-learn 1.9.1.
- [GitHub, odczyt 15:44 UTC](github.json): PR 58 scalony, brak otwartych PR-ów,
  `main` i `ai/implementation` na powyższym SHA. [Required CI](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/actions/runs/36329647835/job/108650401668)
  ma `success`; obszary API, Docker i security przeszły, pięć niezmienionych obszarów
  pominięto. Nie oznacza to ponownego wykonania wszystkich historycznych kontroli.
- W katalogu nadrzędnym nie znaleziono lokalnego checkoutu AI. Odczyt oczekiwanego
  repo `Oskar-Stachowski/retailops-ai-intelligence` zwrócił 404: brak repo lub dostępu,
  nie dowód braku repozytorium w dowolnej lokalizacji. Etap 01 musi ustalić jego lokalizację.
- Dane powstały w osobnych katalogach tymczasowych. Wszystkie 19 śledzonych plików
  `data/demo` zachowało SHA-256. Kod aplikacji, generatora i ML pozostał bez zmian.

[execution.json](execution.json) zawiera konfigurację uruchomień, środowisko,
sumy danych i skryptów audytowych oraz wynik JUnit. [Odtworzenie](reproduction.md)
podaje polecenia. Małe wyniki są w tym katalogu; pełne CSV i surowy JUnit pozostają poza Git.
Integralność plików raportu opisuje [checksums.sha256](checksums.sha256).

## Inwentaryzacja aktualnego kodu — przegląd statyczny

| Obszar | Stan i granica użycia |
|---|---|
| [Makefile](../../../../Makefile), [generator](../../../../data/generator/main.py) | Działające profile `demo/small/medium`, generacja CSV, quality/realism i osobna generacja replay. Profile AI i manifest v2 są planem. |
| [Cechy](../../../../ml/features/demand_forecast.py), [ocena](../../../../ml/evaluation/fixed_origin.py) | Agregaty sprzedaży z availability; dzienny panel, jawne braki, kalendarzowe cechy RF i fixed-origin. Deklaracja kompletnego syntetycznego źródła zastępuje obecnie źródłowe lifecycle/watermarki. |
| [RF](../../../../ml/models/random_forest_forecast.py), [batch](../../../../ml/inference/batch_forecast.py) | Pełny pipeline RF, trzy walidacje i test; batch ładuje oceniony artefakt. Wynik CSV do adaptera API jest diagnostyczny, nie zapisuje predykcji do DB. |
| Pozostałe wyniki | Standalone [baseline](../../../../ml/models/baseline_forecast.py) jest lokalną ścieżką na rzadkich agregatach; porównanie ocenionego RF używa osobnego baseline na wspólnym pełnym panelu. Anomalie i inventory-risk w demo są regułami/scenariuszami, nie ocenionymi modelami anomalii lub stockout. |
| API i persistence | FastAPI, domenowe tabele i metryki streamu istnieją. Bieżące `/forecasts` nie realizuje docelowego kontraktu AI z origin, sklepem, kanałem i lineage. MLflow, AI worker, RAG i Bedrock nie są wdrożone. |
| [Required CI](../../../../.github/workflows/required-ci.yml) | Detekcja zmienionych obszarów, pełne bramki wybranych obszarów, agregator `required-result`; tagi actions i baz obrazów pozostają ruchome (OPS-06). |
| Terraform | Entry point to [infra/environments/dev](../../../../infra/environments/dev/main.tf), zgodnie z `TERRAFORM_DIR` w Makefile; `infra/` nie jest root module uruchomienia. Bez nowego init/plan/apply lub odczytu konta AWS w tym audycie. |

## Generator — wykonane pomiary

Wszystkie liczby poniżej dotyczą **`small`, seed 42, 90 dni, 100 produktów,
5 sklepów, 3 magazynów**, sprzedaż 31.01–30.04.2026. Parametry `days/products/stores/warehouses`
nie były podane w CLI: to rozwiązane domyślne wartości, nie wartości `null` z manifestu.
Kontrast ma jawne `--products 20`. Nie łączymy tej próby ze starym profilem `demo`.

| Kontrola | Zmierzony wynik | Znaczenie |
|---|---|---|
| Determinizm | Dwa uruchomienia: identyczne bajty 17 CSV oraz quality/realism JSON. Manifest różni tylko `generated_at`; po jego wyłączeniu jest identyczny. | Powtarzalna generacja, nie dowód poprawności handlowej. |
| Liczebności | 9000 zamówień, 17 429 pozycji i sprzedaży, 2388 zwrotów, 1300 snapshotów, 18 829 movements; łącznie 67 317 wierszy w 17 CSV. | Pełne row counts i SHA-256 obu uruchomień: [source-measurements.json](source-measurements.json). |
| Identity | 100 i 20 produktów daje ten sam feature `dataset_id`, lecz 12 718 vs 2891 wierszy i różne logiczne SHA-256. Source manifest nie ma `dataset_id` ani checksumów. | DATA-01: nazwa z profilem/datami/seedem nie identyfikuje treści. Obecny assessed RF dodatkowo wiąże hash panelu, więc nie pomija tej kontroli. |
| Daily panel | 5 poprawnych par sklep/kanał; przy założeniu wszystkich aktywnych produktów i dni: 90 × 100 × 5 = 45 000. Rzadki zbiór cech ma 12 718 rekordów (28,26%). Panel ML ma 12 718 dodatnich i 32 282 `complete_zero`. | To **nie** 5 sklepów × 4 dowolne kanały. Uzupełnianie zer wymaga jawnej deklaracji syntetycznej kompletności; bez niej próbka daje `unknown_eligibility`, `units=null`. Brakuje źródłowych statusów i wersji asortymentu (DATA-02). |
| Wymiary | 12 SKU zawiera whitespace (`Pet Care`); 8 kategorii odpowiada dokładnie 8 markom; 4 regiony odpowiadają dokładnie 4 kanałom. | Sztuczne zależności i niewystarczający kontrakt wymiarów (DATA-02). |
| Chronologia i koszyk | 954 sprzedaże przed własnym zamówieniem; 338 koszyków z powtórzonym produktem. Zero różnic sum zamówień oraz quantity/price/amount/currency/product między pozycją a odtworzoną sprzedażą. | DATA-03. Powiązanie pozycja–sprzedaż odtworzono kluczem generatora; CSV sales nie ma bezpośredniego `order_item_id`. |
| Zwroty | Zero zwrotów przed sprzedażą i zero nadmiarowych zwrotów w wygenerowanym zestawie. Opóźnienie 0,9167–94,25 dnia; wszystkie zwroty przypadają na 1–5 maja. | Obecna generacja zależy od końca całej próby, nie okna zwrotu własnej sprzedaży. Wymagany return tail i reguły kategorii/kanału (DATA-03). |
| Cena | Dokładnie jedna deklarowana cena pokrywa 11 756/17 429 sprzedaży: **67,4508%**. 5673 bez ceny; zero overlap przy domkniętych granicach. | DATA-04. Cena regularna może różnić się z powodu rabatu; osobno zmierzono 2319 różnic także po zastosowaniu deklarowanego aktywnego rabatu i zaokrąglenia HALF_UP. |
| Promocja | 2866 sprzedaży z flagą; 2197 flag bez aktywnej promocji katalogowej, 1936 sprzedaży w aktywnej promocji bez flagi. | DATA-04: rozłączne funkcje kalendarza i transakcji. Przykłady oraz zakresy są w JSON. |
| Zakres dat | Manifest kończy się 30.04; pomija 2388 zwrotów w maju, 100 przyszłych cen od 31.05, końce promocji 14–17.05 i 350 forecastów z końcem 7–13.05. | DATA-01: potrzebne zakresy per tabela, rozdzielenie historii/planów/tail i watermarks. Przyszły plan sam w sobie nie jest błędem. |
| Inventory | 1300 `initial_stock` dla 300 par produkt/magazyn; każda para ma 4–5 otwarć, łącznie 1000 nadmiarowych. | DATA-06: snapshot nie może ponownie otwierać ledgeru. Nie blokuje wariantu forecast-only bez inventory. |
| Quality | 15/15 starych checks przechodzi. Niezależne wstrzyknięcie zwrotu przed sprzedażą oraz skumulowanego nadmiarowego zwrotu nadal daje `passed`. | DATA-05: zielony raport strukturalny nie jest bramką gotowości AI. |

Dodatkowy **przegląd statyczny** [profile_engine.py](../../../../data/generator/profile_engine.py)
i [pricing.py](../../../../data/generator/pricing.py) potwierdził:

- `normal_daily_sales` zawiera demand weight, który commerce mnoży ponownie;
  komplementarne produkty są wybierane od początku listy, także z powtórzeniem bazowego SKU.
- Indeks czasu biegnie wstecz: `post_promo_dip` wypada 2–5.04 **przed** promocją
  6–20.04, a `pre_promo_softening` 21–23.04 **po** niej. Katalog promocji stosuje jeszcze inne daty.
- Ceny nie mają scope ani wersjonowanej dostępności; `created_at` zależy od indeksu
  produktu. Promocje mają `channel=all`, bez `known_at`, lokalizacji i historii wersji.
  Obecny RF nie korzysta z tych pól; nie wykazujemy przez to leakage zapisanej oceny.
- Movement sprzedaży dostaje magazyn przez indeks modulo, bez wersjonowanego
  mapowania fulfillment sklep→magazyn. Nie istnieje uzgodniony ledger ani wiarygodne etykiety stockout.
- Truth (`latent_demand`, noise, multipliers, stockout, DQ labels) jest w sales CSV.
  Aktualna lista cech RF je wyklucza, ale przyszły eksport musi fizycznie rozdzielić truth i dane operacyjne.

## ML — wykonane próby i zachowane ograniczenia

Próba z lukami w datach dała lag1=0/**unavailable**, lag7=7/**available** i dwie
obserwacje w siedmiodniowym oknie. Dopisanie przyszłego dnia nie zmieniło cech.
Zmiana ceny/promocji/stockout/inventory/truth targetu również ich nie zmieniła;
lista 18 wejść RF w JSON nie zawiera tych pól. Nie ma przyszłego inventory fallback
w używanym torze forecastingu ani potrzeby przyjmowania nieznanego zapasu za zero.

ML-07 pozostaje: późna sprzedaż historycznego dnia przesuwa availability całej sumy;
przy tym samym starym origin lag1 zmienia się **3→0**, available **1→0**.
Wymagana jest wersjonowana historia w AI 03 przed odbiorem AI 04. Ta próba
nie dowodzi błędu starego, kompletnego syntetycznego panelu RF.

Dla `y=0, yhat=100`: WAPE/MAPE są null, status `not_evaluable`, MAE i bias=100,
nadmiarowa prognoza na zerze=100. Pusta próba ma null metryk i zero ocenionych wierszy.
Łącznie **138 testów przeszło, 0 pominiętych** w 4,87 s. Testy runnera opisują
również obecny commit błędnego JSON; ich sukces nie zamyka OPS-03.

[ml-verification.json](ml-verification.json): sprawdzono 12 checksumów zachowanego
evidence oraz po 9 artefaktów dwóch RF80. `load_assessed_run()` odtworzył prognozy
testu z zapisanego modelu; każdy przebieg ma 9000 wierszy panelu i 2800 zapisanych
prognoz walidacji/testu. Świeży diagnostyczny batch dał 700 prognoz z tą samą tożsamością
modelu/runu co wcześniejszy batch. Status pozostał **`rejected`**.

Nie przeprowadzano nowego treningu ani wyboru modelu. Zachowane
[wyniki RF](../../ml/fixed-origin-rf-2026-09-27/README.md) to WAPE RF80=159,8564%
vs moving average=148,1966%; źródło treningu `97a4aa6`, model
`sha256:571d1b303e2fe1c11b31ea88b79c100d1e6497d3447cd2e995435192a60667ab`.
W AI 04 trzeba ocenić modele na nowym zwalidowanym snapshotcie. Baseline może
zostać championem dopiero po przejściu tej oceny i polityki AI 05.

## Zdarzenia i API — wykonane próby offline

[contracts.json](contracts.json) powstał z rzeczywistego generatora, parsera
envelope, consumera, runnera i OpenAPI. Repozytorium DB i klient Kafka były mockami;
nie uruchomiono brokera ani zapisu domenowego.

| Kontrola | Wynik |
|---|---|
| Registry i routing | 49 856 zdarzeń, 13 typów. Generator i consumer mają zgodne mapowanie, Compose inicjalizuje wszystkie 5 używanych tematów oraz DLQ. Registry pomija `return_completed`/`replenishment_completed` i `retailops.intelligence.v1`, deklaruje nieemitowane `orders.v1`/`ml.v1` (OPS-07). |
| Walidacja envelope | Wszystkie wygenerowane envelope przyjęte. Przyjęto też osobno brak `topic`, błędny temat, `schema_version=999` i pusty payload. Registry jest opisem, nie wykonywalnym JSON Schema typów payloadu (OPS-07). |
| Tożsamość zdarzenia | W kontrastowych snapshotach 100 vs 20 produktów: 8501 wspólnych event IDs ma różne payloady. Brak duplikatów ID wewnątrz pierwszego zestawu. ID wiąże seed/type/natural key, bez snapshot/version; wspólny replay różnych zestawów może zostać potraktowany jako duplikat (OPS-07). |
| ACK/DLQ | Invalid JSON: commit=1, próby zapisu błędu=0. Awaria handlera: commit=1, próba zapisu błędu. Awaria DB **i** kwarantanny/state: commit=1 mimo nieudanego zapisu. Licznik dead-letter nie dowodzi trwałości (OPS-03). |
| Projekcja forecast | Zdarzenie dostaje `processed`; wykonano tylko dedup, event log, metric observations i consumer state. Domyślne handlery są `_noop_handler`. Projekcja AI do domenowego read modelu jest zakresem AI 10. |
| List API | OpenAPI siedmiu list potwierdza limit/offset i bounded pagination; 14 żądań z limit=0 lub offset=−1 zwraca 422. Nie wykonano nowych poprawnych list queries z DB. |
| Pola API | `/sales`: brak store/order/item/ingested-at w response. `/forecasts`: produkt i okres, bez daily store/channel/origin/source/model lineage. `/inventory-risks`: produktowa heurystyka, bez skalibrowanego probability i grain fizycznej lokalizacji. Potrzebne nowe kontrakty/adaptery w AI 05/08/10. |
| Auth | `GET /me?user_id=platform-admin` daje 200 i `auth_mode=local_mock`. Tożsamość wybiera klient; granica jest jawnie demonstracyjna. Własne auth AI od 01, integracja uprawnień przed 10–12. |

## Decyzja per zastosowanie

| Zastosowanie / przejście | Warunek dalszej pracy |
|---|---|
| **AI 01** | Odblokowane. Pierwszy mały PR: osobne repo, ADR granic, importowalny pakiet, lock i minimalne CI. [Dokładny zakres](../../../plans/ai/backlog.md). |
| **AI 02 → 03** | Zamknąć DATA-01–05; następnie importer/curated i ML-07. Pierwszy PR 02 ograniczyć do konfiguracji/manifestu/identity, zachowując demo. |
| **AI 04 → 05, forecast-only** | Źródło i snapshot po swoich bramkach; nowe baseline/RF, zamrożony test, lifecycle i serving. Nie wymaga pełnego procurement ani inventory features. |
| **AI 06–09, stockout/anomaly** | DATA-06, właściwe etykiety i bramki czasowe; ponowna wersja danych i ocena. Aktualne `stockout_ready=false`, `anomaly_ready=false`. |
| **AI 10–12** | OPS-03/07, domenowe projekcje, nowe API/auth; dopiero potem narzędzia agenta. RAG 11 może rozpocząć się po 01 zgodnie z planem. |
| **AI 13–16** | Własne odbiory telemetry/security/releases, OPS-06 i infrastruktury. Ten audyt nie zastępuje prób runtime, awarii, migracji, kosztów ani cleanup AWS. |

Aktywne problemy i kryteria zamknięcia są wyłącznie w
[otwartych ustaleniach](../../../audits/open-findings.md); kolejność implementacji
w [backlogu](../../../plans/ai/backlog.md). Nie ma pozostałych prac w zakresie tego audytu.
