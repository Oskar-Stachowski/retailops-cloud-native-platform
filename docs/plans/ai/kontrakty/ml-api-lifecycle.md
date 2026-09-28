# Kontrakt ML, API i lifecycle

**Status:** docelowa specyfikacja wdrożenia, nie opis aktualnie działającego API RetailOps. Wersja planu: 1.1. Kontrakt dotyczy AI; istniejące endpointy RetailOps i ich adaptery są opisane w [integracji](integracja-agent.md). Semantykę danych/identity/czasu definiuje [dane-i-czas.md](dane-i-czas.md), progi/profile [profile-i-bramki.md](profile-i-bramki.md).

W etapie 01 wdrożono wybrany forecast wire contract v1 oraz walidację offline
dataset/feature/label/split/model/prediction/run/tool/bundle w repo AI.
[Odbiór](../../../evidence/ai/01/README.md) wskazuje kod i ograniczenia: schemas
nie implementują importu, workerów, modeli, tool executora, auth ani streamingu.

## 1. Granice modeli i targetów

| Zastosowanie | Registry name | Baseline | Kandydaci | Target / grain |
|---|---|---|---|---|
| Forecast | `retailops-demand-forecast` | last observed, moving average, seasonal naive7 | RF, HGB; Keras challenger09 | `observed_sales_units`; origin × target date × produkt × sklep × kanał |
| Anomaly | `retailops-sales-anomaly` | DQ rules + seasonal residual | IsolationForest | anomalia obserwowanego okna; jawnie observation/episode |
| Stockout | `retailops-stockout-risk` | LogisticRegression | HGBClassifier | nowy stockout w `(as_of,as_of+7d]`; produkt × fizyczna lokalizacja zapasu |

Modele zwracają sygnały do oceny człowieka. Prognoza obserwowanej sprzedaży nie oznacza nieograniczonego popytu; explanation nie oznacza udowodnionej przyczyny. Current stockout to osobny status, nie pozytywna predykcja przyszłego zdarzenia. Wszystkie wejścia mają provenance i cutoff; dane `simulation_only` są niedopuszczalne w feature matrix.

## 2. Wspólny kontrakt eksperymentu i ewaluacji

Każdy training/evaluation run zapisuje co najmniej:

| Grupa | Pola / artefakty |
|---|---|
| Identyfikacja | `run_id`, `task`, `model_family`, `run_status`, `created_at`, `started_at`, `completed_at` |
| Dane | `source_dataset_id`, `curated_dataset_id`, `feature_set_id`, `label_dataset_id` gdy dotyczy, `split_id`, schema/contract versions, artifact checksums |
| Pochodzenie | source repo SHA, AI repo SHA, dependency lock hash, config hash, data seed, model seed, environment/platform |
| Czas | train/validation/calibration/test boundaries, origin policy, `training_cutoff`, target/horizon, label eligibility, split-gap policy |
| Model | hyperparameters, preprocessing, signature/input example, full serialized pipeline, framework/flavor, artifact checksum |
| Wyniki | metric definition version, aggregate/segment metrics, liczebności/coverage/validity, baseline deltas, threshold/calibrator/interval versions |
| Decyzja | gate outcomes, evaluation protocol, report, model card, reject/promote reason, reviewer/decision ID |
| Zasoby | training duration, peak memory, model size, cold load i inference duration/latency |

W 04 dopuszczalny jest plikowy sink z tym kontraktem. W 05 ten sam interfejs loguje do MLflow. Historyczny import zachowuje oryginalne run ID i faktyczne czasy; ma pole `imported_at`, zamiast podszywać się pod nowy trening.

Train/validation/calibration/test oznaczają role danych, nie tylko nazwy katalogów. Nie wolno dopasowywać preprocessingu, wyboru hiperparametrów, kalibracji, progów ani przedziałów na final test. Historyczne forecasty używane downstream mają dodatkowo upstream model/config/feature IDs oraz poprawny historyczny training i selection cutoff. Wyprodukowanie pliku dziś nie narusza PIT, jeśli odtworzono wyłącznie wiedzę dostępną w origin.

### Ważność metryk

Wynik metryki zawiera `value`, `unit`, `status`, `n_total`, `n_evaluable`, `coverage`, `reason` i, gdzie potrzebny, mianownik/positive count. `status` metryki: `evaluable`, `not_evaluable`; gate osobno według profile-i-bramki: `passed`, `warning`, `failed`, `not_ready`, `not_evaluable`, `not_applicable`. Null nigdy nie zamienia się w zero.

- WAPE = `sum(abs(y-yhat))/sum(abs(y))` na tym samym zbiorze obserwacji wszystkich modeli; domyślna jednostka `ratio` (0.12 = 12%). Przy zerowym mianowniku `null/not_evaluable`, obok MAE i suma nadmiarowej prognozy na zerach. `y=[0]`, `yhat=[100]` daje MAE100, nie perfekcyjny WAPE.
- MAE i RMSE mają jednostkę `units`; bias definiuj jako średnią `yhat-y` w units. Procentowy bias jest osobną metryką i przy zerowym denominatorze jest niezdefiniowany.
- MAPE wyłącznie pomocniczo, na jawnie określonych dodatnich obserwacjach i z coverage.
- PR-AUC ma podaną implementację/konwencję (np. average precision), prevalence i liczebności klas. Metryka niezdolna do oceny wymaganej cechy z powodu braku klas ma status `not_evaluable`.
- Anomaly precision/recall/false-alert rate/delay mają jednostkę per observation albo per episode oraz zasady zero-positive i repeated alerts.
- Intervals/calibration mają próbę kalibracyjną, wersję, nominal/empirical coverage i ograniczenia. Nie używaj dowolnych procentów jako „confidence interval”.

Gates krytycznych segmentów wymagają minimum próbki i ważnej metryki. `not_ready` nie jest sukcesem; waiver, jeśli dopuszczony polityką, ma jawny zakres i nie zmienia failed metryki w passed. Smoke może zaliczyć wykonanie ścieżki bez spełnienia portfolio model-quality gate.

## 3. Registry, release i promocja

MLflow backend PostgreSQL i artifact store są odrębnymi zasobami. Rejestr zawiera trzy nazwy z tabeli; aliasy `candidate`, `champion`, `rollback` wskazują wersje immutable. Stany biznesowe experimental/candidate/rejected/champion/archived implementuj tagami i audytem; nie polegaj na przestarzałych stage semantics.

`Training succeeded` oznacza zakończenie procesu, nie zgodę na serving. Promocja wymaga source/feature gates, poprawnego PIT, evaluation protocol, segment gates, signature i load smoke, zasobów w budżecie, security/license checks, model card i jawnego review. W 05 wymagany jest minimalny drift/freshness compatibility check z wersjonowanym reference; pełny scheduler/taxonomy/reporting dochodzi w13. Nie oznaczaj nieuruchomionego monitoringu jako passed.

Release manifest zawiera co najmniej:

```json
{
  "release_id": "release-forecast-001",
  "image_digest": "sha256:<image-checksum>",
  "model_name": "retailops-demand-forecast",
  "model_version": "12",
  "artifact_sha256": "<artifact-checksum>",
  "feature_schema_version": "forecast-features-v1",
  "config_hash": "<config-checksum>",
  "evaluation_id": "eval-001",
  "decision_id": "decision-001",
  "previous_release_id": null
}
```

Są to przykładowe wartości, nie istniejące release’y. Alias jest wygodą wyboru przed release’em. **Runtime/retry/restart korzysta z wersji i checksumu przypiętego w release**, nie rozwiązuje aliasu na każdy request ani start procesu. Inference run kopiuje tę wersję i nie może zmienić jej w trakcie joba.

Docelowe operacje CLI/CI: review, reject, promote, rollback. Każda mutacja zapisuje `decision_id`, principal, time, from/to versions, evidence/approval reason, phase/status i before/after alias/runtime state. First release ma jawny brak poprzednika; do demonstracji rollback potrzebne są dwie działające wersje. Retencja nie usuwa artefaktów bieżącego ani rollback release’u.

MLflow alias update, DB audit i Git desired state nie są jedną transakcją. Stosuj blokadę na model, idempotentny decision ID, kroki przygotowanie→weryfikacja→zmiana→smoke→commit decision i recovery/compensation. Po awarii odczytaj faktyczny stan; nie uznawaj częściowej promocji za sukces. Rollback przypina zgodny pakiet model+preprocessing+schema+threshold+config, a później image/Helm/prompt/index zgodnie z runbookiem platformy. Brak re-embedding/retraining jako warunku zwykłego rollback.

## 4. Wspólne API i autoryzacja

**AI base path:** `/api/v1`; JSON, UTC ISO8601 dla timestampów, `YYYY-MM-DD` dla dat biznesowych z jawnym calendar timezone (domyślnie UTC). Kontrakty typed schemas generują OpenAPI; przykłady i zmiana implementacji w tym samym PR. Pola źródłowego RetailOps nie są automatycznie identyczne.

Nagłówki: `Authorization`, `X-Correlation-ID`, `traceparent`; mutacje runów wymagają `Idempotency-Key`. Opcjonalny `X-API-Version` informuje o serwowanym kontrakcie. Serwer generuje bezpieczny correlation ID, jeśli go brak, i nie ufa klientowi w zakresie role/scope. Nie loguj tokenów, pełnych promptów, sekretów ani dowolnych ścieżek artefaktów.

| Rola | Uprawnienia docelowe |
|---|---|
| `viewer` | autoryzowane predykcje, rekomendacje, modele/evaluations/drift i bezpieczne metadane runów |
| `operator` | viewer + ograniczone zapytania asystenta |
| `pipeline` | tworzenie przypisanych runów forecast/anomaly/stockout i techniczny zapis wyników przez wewnętrzny worker |
| `admin` | kontrolowane workflow treningu/indeksowania i operacje administracyjne; nie publiczny dowolny filesystem |
| `promoter` | reviewed promotion/rollback przez CLI/CI |

Role nie są automatycznie hierarchiczne; jawna konfiguracja przypisuje capabilities. Każdy odczyt listy, konkretnego runa, evaluation i trace podlega scope. Uprawnienia z uwierzytelnionego principal przecinają requested scope. Parametr `requested_by` wyznacza serwer. Auth RetailOps demo nie jest kompletnym IdP; integrację i agent principal opisuje [integracja-agent.md](integracja-agent.md).

Domyślna paginacja: `limit=50`, maksymalnie 200; konfiguracja może ustalić niższe limity dla narzędzi agenta. Sortowanie stabilne po kluczu i ID; date range i liczba encji są ograniczone wersjonowaną konfiguracją. `items` plus `pagination:{limit,offset,total}` i `generated_at`; sortowanie nie zastępuje protokołu snapshot eksportu. Czytanie większej liczby stron musi używać zidentyfikowanego output/run albo jawnej semantyki aktualizowanego widoku.

Problem details zawiera `type`, `title`, `status`, `detail`, `instance`, `correlation_id`, opcjonalne bezpieczne `errors:[{field,code,message}]`. Statusy: 401 brak tożsamości, 403 brak capability, 404 nieistniejący/niewidoczny zasób zgodnie z polityką, 409 konflikt tożsamości/idempotencji/stanu, 422 walidacja/scope, 429 limit, 503 wymagana dependency unavailable. Nie ujawniaj stack trace, tokenu, pełnego promptu ani ścieżki model binary.

## 5. Trwały run i idempotency

Run command zwraca `202 Accepted`, `Location` i zapisany run, dopiero gdy przyjęcie jest trwałe. Schema:

```json
{
  "run_id": "run-001",
  "run_type": "forecast_batch",
  "status": "queued",
  "requested_at": "2026-08-23T00:00:00Z",
  "started_at": null,
  "completed_at": null,
  "requested_by": "pipeline-identity",
  "input_ref": {"source_dataset_id": "source-001", "as_of": "2026-08-22T23:59:59Z"},
  "resolved_model": {"name": "retailops-demand-forecast", "version": "12"},
  "output_ref": null,
  "error": null
}
```

Właściwe identyfikatory są generowane przez implementację; krótkie ID w przykładach służą czytelności. `run_type` obejmuje forecast_batch, anomaly_detection, stockout_risk oraz typy administracyjne opisane w integracji. `resolved_model` jest nullable: run indeksowania/RAG bez klasycznego modelu ma null i własne wersjonowane `input_ref`/index config, zgodnie z integracja-agent.md. Statusy: queued→running→succeeded/failed/cancelled. Requeue po utracie lease zapisuje attempt history; `failed` nie zmienia się po cichu w succeeded bez jawnego retry/attempt. `output_ref` wskazuje wyłącznie kompletny, zatwierdzony output. Brak częściowych rekordów w domyślnym read API.

Key jest namespaced przez principal + endpoint; przechowuj request canonical hash i run ID atomowo. Identyczne key/request zwraca istniejący run; ten sam key z innym request daje409. Retencja idempotency wynosi co najmniej wersjonowany maksymalny retry window (docelowo np.7 dni; zatwierdź wraz z timeout/replay policy). Unique output key i content identity pozostają niezależną ochroną po wygaśnięciu key. Retry nie tworzy nowych predictions dla tego samego run/partition.

## 6. Endpointy forecast

| Endpoint | Rola / funkcja |
|---|---|
| `POST /api/v1/forecast-runs` | pipeline; kolejkuje bounded batch |
| `GET /api/v1/forecast-runs/{run_id}` | autoryzowane metadane runa |
| `GET /api/v1/forecasts` | scoped persisted outputs |

Przykładowy request: `{"as_of":"2026-08-22T23:59:59Z","horizons_days":[7,14],"product_ids":["p-101"],"store_ids":["s-03"],"channel":"store","model_alias":"champion"}`. Pola horizon oznaczają pokrycie dziennych dat 1..7/1..14 od origin: wspólny dzień jest zapisywany raz, nie jako duplikat obu okien. `model_alias` dopuszcza jedynie alias zgodny z zatwierdzonym release’em; serwer zapisuje immutable resolved version, nie pozwala klientowi wybrać niezatwierdzonego modelu. Puste filtry oznaczają pełny **autoryzowany** zakres w limitach batch policy, nie nieograniczoną całą bazę.

Lista filtruje po `product_id`, `store_id`, `channel`, `target_from`, `target_to`, `as_of`, opcjonalnym `inference_run_id`, `limit`, `offset`. Jawny `as_of` wybiera konkretny origin; bez niego API wybiera najnowszy kompletny kwalifikujący się output dla danego klucza i ujawnia origin. Starszy replay nie nadpisuje nowszego origin.

Forecast item:

```json
{
  "forecast_id": "forecast-001",
  "product_id": "p-101", "store_id": "s-03", "channel": "store",
  "forecast_origin": "2026-08-22T23:59:59Z",
  "target_date": "2026-08-25", "horizon_days": 3,
  "target_type": "observed_sales_units", "unit_of_measure": "unit",
  "predicted_units": 42.5,
  "interval_lower": 31.0, "interval_upper": 55.0,
  "interval_method": "validation_residual_quantiles", "nominal_coverage": 0.9,
  "model_name": "retailops-demand-forecast", "model_version": "12",
  "release_id": "release-forecast-001",
  "source_dataset_id": "source-001", "feature_set_id": "features-001",
  "inference_run_id": "run-001", "generated_at": "2026-08-23T00:02:00Z",
  "freshness_status": "current", "quality_status": "passed"
}
```

Origin zamyka dzień biznesowy D (domyślnie UTC), a `target_date=D+horizon_days`; implementacja ma przykłady graniczne. W przykładzie cutoff ma dokładność jednej sekundy; dokładność i granicę domknięcia zapisuje konfiguracja, a `available_at` nadal obowiązuje. Brak ocenionego interval oznacza nulls + reason, nie arbitralne ±20%. Prognozy nieujemne mają jawnie udokumentowany clipping/transform i tę samą regułę w ewaluacji. Waluty i jednostki nie są niejawnie agregowane.

## 7. Endpointy anomaly

`POST /api/v1/anomaly-detection-runs` (pipeline), `GET /api/v1/anomaly-detection-runs/{run_id}`, `GET /api/v1/anomalies`, `GET /api/v1/anomalies/{anomaly_id}`. Request: `as_of`, `window_from`, `window_to`, bounded product/store/channel scope, zatwierdzony detector release. Obserwowane okno kończy się nie później niż pozwala cutoff kompletności danych. Nie wolno produkować anomalii dla przyszłej sprzedaży.

Lista filtruje product/store/channel, type, severity, status, detected_from/to i paginację. Item zawiera `anomaly_id`, grain, `observed_window`, `detected_at`, `as_of`, `anomaly_type`, `severity`, `status`, `observed_units`, `expected_units`, `residual`, `score`, `score_definition`, `explanation_codes`, `inventory_context`, `promotion_context`, `detector_name/version`, `release_id`, `threshold_version`, source/feature/run IDs i freshness. Typy obejmują sales_spike, sales_drop, residual_outlier, return_spike, stockout_censored_demand, data_quality_suspicion; nie każdy typ musi być wynikiem tego samego modelu.

Episode ID i dedup policy wiążą powtarzające się alerty. `insufficient_data` jest kontrolowanym wynikiem oceny/coverage; nie twórz z niego udawanego alertu z zerowym score. Pole status opisuje operacyjny stan alertu; brak write endpointu oznacza brak automatycznej zmiany statusu przez agenta.

## 8. Endpointy stockout

`POST /api/v1/stockout-risk-runs` (pipeline), `GET /api/v1/stockout-risk-runs/{run_id}`, `GET /api/v1/stockout-risks`, `GET /api/v1/stockout-risks/{risk_id}`. Request: `as_of`, `horizon_days=7`, bounded product/stock_location IDs, approved model release/threshold version. Lista filtruje product, stock_location, mapping-supported store, risk_band, status, as_of, run ID i paginację. Filtr channel jest dozwolony tylko dla rzeczywiście partycjonowanego inventory zgodnie z kontraktem08.

```json
{
  "risk_id": "risk-001", "product_id": "p-101", "stock_location_id": "wh-03",
  "as_of": "2026-08-22T00:00:00Z", "horizon_days": 7,
  "status": "scored", "probability": 0.82, "risk_band": "high",
  "threshold_version": "stockout-policy-v1", "calibrator_version": "cal-v1",
  "model_name": "retailops-stockout-risk", "model_version": "7",
  "release_id": "release-stockout-001",
  "top_factors": [{"code":"low_days_of_supply","direction":"increases_risk"}],
  "inventory_freshness_status": "current", "freshness_status": "current",
  "source_dataset_id": "source-002", "feature_set_id": "stockout-features-001",
  "inference_run_id": "risk-run-001", "generated_at": "2026-08-22T00:03:00Z"
}
```

Statusy: scored, already_stockout, insufficient_data, stale_input. Dla trzech ostatnich probability/risk_band są null z explanation, nie odpowiednio 1/0/low. Aktualny brak zapasu może mieć osobny priorytet operacyjny, nie fałszywe model probability. `top_factors` wskazują fakty/cechy, nie udowodnioną przyczynowość. Source warehouse mapping i forecast upstream lineage muszą być dostępne do audytu.

## 9. Modele, evaluations, drift i pozostałe rodziny

| Endpointy | Wymagane dane / etap |
|---|---|
| `GET /api/v1/models` | models list + aliases, deployment state, card ref; 05, rozszerzenie07/08 |
| `GET /api/v1/models/{model_name}` | candidate/champion/rollback, deployed immutable version, evaluation/drift refs, feature schema |
| `GET /api/v1/models/{model_name}/versions` | paginated versions, run/artifact checksum, status, framework |
| `GET /api/v1/evaluations/{evaluation_id}` | protocol/split/dataset IDs, metrics z validity, gate outcomes, safe artifact refs |
| `GET /api/v1/drift-reports` | model/task/date/status filters, sample counts, freshness; pełna implementacja13 |
| `GET /api/v1/drift-reports/{report_id}` | reference/current datasets, drift methods, segments, thresholds, mature-label coverage, actions |
| `GET /api/v1/recommendations` i `/{recommendation_id}` | persisted recommendations; dokładny schemat/policy w integracja-agent.md, requires_human_review=true |
| Assistant query/run APIs | kompletna specyfikacja w integracja-agent.md; nie duplikuj schematu tutaj |
| Knowledge index administration APIs | kompletna specyfikacja w integracja-agent.md; admin/internal only |

Model API rozróżnia registry alias od faktycznie deployed version. Drift status może być passed/warning/failed/insufficient_data/not_run; nie zmyślaj wyniku dla nieuruchomionego etapu. Raporty przechowują reference definition, sample sizes, threshold config i scope. Performance drift wykorzystuje wyłącznie dojrzałe outcome windows; brak etykiety nie jest błędną predykcją.

Brak publicznego HTTP promotion lub endpointu wykonującego rekomendację. Opcjonalny `POST /api/v1/predictions/stockout-risk` jest odłożony do czasu rzeczywistej potrzeby: wymaga wersjonowanego feature payloadu, PIT validation, auth i pinned model; nie jest konieczny do pełnego batch-first zakresu v1. Feedback asystenta również nie jest automatycznym online learning.

Poza base path: `GET /health` (proces), `/ready` (dependencies roli), `/metrics` (wewnętrzna telemetry), `/version` (code/image/release i resolved model info). Brak Bedrock obniża gotowość agenta, ale nie klasycznych read API. Nie ujawniaj sekretów przez diagnostykę.

## 10. Output, outbox, świeżość i wersje

Prediction ID wiąże logical key, origin, model/config oraz run/output identity według kanonizacji danych; checksum bajtów jest odrębny od content hash. Staging przechodzi count/domain/unique checks; complete output jest publikowany atomowo. Dotychczasowy output pozostaje odczytywalny zgodnie z freshness/retention. `generated_at` nie zastępuje origin ani source watermark.

W10 publikacja wyniku i zapis transactional outbox są jedną transakcją. Publisher działa co najmniej raz, więc `event_id` i consumer dedup są konieczne; inference success i event delivery status są oddzielne. Docelowe pełne AI outputs trafiają na **nowy `retailops.intelligence.v2`** zgodnie z ADR-09; legacy `.v1` zachowuje dotychczasowy kontrakt demo. Canonical envelope, payloady i projekcja RetailOps są własnością [integracja-agent.md](integracja-agent.md), nie należy ich implementować drugi raz w module ML.

Freshness jest obliczana względem source watermark, cutoff, origin i harmonogramu danego taska. `current`, `stale`, `unknown` mają wersjonowane progi w konfiguracji. Sam świeży `generated_at` po ponownym scoringu starych danych nie daje `current`.

API additive optional fields mogą pozostać w `/api/v1`; breaking grain/semantics/name change wymaga nowego kontraktu/major i adaptera. Wersja API AI v1 i topic intelligence.v2 oznaczają różne kontrakty — ich numery nie muszą być równe. OpenAPI/JSON schema examples i consumer fixtures zmieniają się razem z kodem.

## 11. Minimalne acceptance evidence

1. OpenAPI snapshot + positive/negative schema fixtures, pagination/limits/auth/scope, idempotency conflict i safe errors.
2. PIT oraz metryki zer, brak klas, coverage, segment gates i wspólne oceniane klucze.
3. Complete run → immutable model → persisted output → read API z identyczną lineage.
4. Worker crash/retry bez częściowej publikacji; future alias update nie zmienia running/pinned release’u.
5. Reject bez deploy; promote i rollback z audytem; uszkodzony model/signature blokuje publikację.
6. Po10 duplikat eventu nie dubluje projekcji, starszy replay nie nadpisuje nowszej predykcji; nie myl powodzenia publish z akceptacją domenową.
7. Po13 etykiety niedojrzałe nie psują performance drift; failed drift blokuje promocję zgodnie z polityką, nie uruchamia samoczynnego champion update.

Wszystkie wykonane polecenia i rezultaty trafiają do [evidence](../szablony/karty-i-evidence.md). Powyższe przykłady nie są wynikami testów ani deklaracją, że endpoint już istnieje.
