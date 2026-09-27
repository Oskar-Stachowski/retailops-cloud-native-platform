# Kontrakt integracji RetailOps, RAG i agenta

**Wersja planu:** 1.1. Proponowane interfejsy do wdrożenia w etapach 10–12. Mapę istniejących zasobów RetailOps w sekcji 1 należy potwierdzić w aktualnym OpenAPI przed implementacją klienta. Pozostałe sekcje opisują docelowe rozwiązanie, bez deklaracji wdrożenia endpointów AI, auth, pgvector lub Bedrock.

Wspólne typy run, błędów, nagłówków, list, metadanych modelu, idempotency oraz REST ML definiuje [ML API i lifecycle](ml-api-lifecycle.md). Dane i PIT definiuje [kontrakt czasu](dane-i-czas.md). W tym pliku obowiązują integracja źródła, zdarzenia, RAG, narzędzia, Assistant API, administracja indeksu oraz struktura sugestii. Definicji ML nie kopiujemy do drugiego kontraktu.

## 1. Mapa integracji z API RetailOps

Poniższe ścieżki są zasobami RetailOps, a nie AI `/api/v1`. Bazowy adres należy odczytać z konfiguracji deploymentu; nie dopisywać automatycznie prefiksu AI.

| Odczyt | Faktyczne filtry domenowe | Ograniczenie danych |
|---|---|---|
| `GET /products` | `category`, `status`, `search` | Produkt nie zastępuje historii assortment i mappingu lokalizacji. |
| `GET /sales` | `product_id`, `channel`, `currency`, `sold_from`, `sold_to` | Brak `store_id`, `order_id`, `ingested_at`; `created_at` nie dowodzi dostępności historycznej. |
| `GET /inventory-snapshots` | `product_id`, `warehouse_code`, `unit_of_measure`, `recorded_from`, `recorded_to` | Warehouse wymaga wersjonowanego mappingu do lokalizacji/grainu AI. |
| `GET /forecasts` | `product_id`, `status`, `method`, `date_from`, `date_to` | Okresowy forecast produktowy, nie dzienny store/channel. |
| `GET /inventory-risks` | `risk_status`, `category` | Produktowa heurystyka `risk_status`, nie modelowe prawdopodobieństwo. |
| `GET /dashboard/live-operations` | Sprawdzić bieżące OpenAPI przy implementacji | Read model operacyjny; nie eksport pełnej historii. |

Pierwszych pięć list używa `limit=50` domyślnie, zakresu `1..100`, `offset>=0`, `sort_by`, `sort_order`. Dozwolone wartości sortowania są różne per resource i klient pobiera je z przypiętego OpenAPI. Obecny kształt listy:

```json
{"items": [], "pagination": {"limit": 50, "offset": 0, "total": 0}}
```

Nie wymagaj tu `generated_at`: to proponowane pole list AI, nie istniejącej listy RetailOps. `GET /sales?sold_from=2026-04-01T00%3A00%3A00Z&sold_to=2026-04-30T23%3A59%3A59Z&limit=100&offset=0&sort_by=sold_at&sort_order=asc` ilustruje aktualne nazwy parametrów. W kliencie stosuj poprawny URL encoding, nie sklejaj parametrów ręcznie.

Typowany klient sprawdza schemat i świeżość, propaguje `X-Correlation-ID`/`traceparent`, ogranicza timeout/retry/circuit breaker. Czytając stare zasoby, nie wymyśla brakującego sklepu ani zamówienia. Potrzebne rozszerzenia i eksporty powstają upstream w RetailOps; AI nie łączy się bezpośrednio z jego bazą. Nie kopiuj generatora ani całego `ml/` do repo AI.

## 2. Snapshot, REST i przekazanie do strumienia

1. Bazą jest immutable file snapshot z etapu 03, identyfikowany canonical content hash i manifestem. REST służy też ograniczonym bieżącym odczytom; samo przejście wszystkich stron nie jest spójnym snapshotem.
2. Historyczny eksport REST wymaga `snapshot_id`, utrwalonego zbioru/wersji rekordów i deterministycznej paginacji. Alternatywny protokół watermark/cursor musi zachować wersje widoczne na cutoff. Bez tego nie deklaruj spójności przy równoczesnych insert/update/delete.
3. Manifest przejścia zawiera `snapshot_id`, source/schema versions, cutoff event time i availability, wektor `{topic, partition, included_through_offset}` oraz informację, jak zdarzenia/fakty zostały uwzględnione. Musi istnieć spójne powiązanie snapshotu z logiem, np. eksport z transakcyjnym outbox/źródłowym checkpointem; przypadkowy odczyt bieżącego końca topicu nie wystarcza.
4. Po pełnym, atomowo zatwierdzonym imporcie zacznij od `included_through_offset+1` dla każdej partycji. Dla nakładającego się replay stosuj inbox i natural key/version curation; nie sumuj ponownie już obecnej sprzedaży. Offset Kafka sam nie rozpoznaje identycznego faktu z innym envelope ID.
5. Spóźnione korekty aktualizują wkład właściwej wersji faktu i zachowują availability time; nie nadpisuj historycznej wiedzy dostępnej przy wcześniejszej prognozie. Zasady korekt/tombstones są jawne i wersjonowane. Obsługa nieznanego rodzaju korekty kończy się kwarantanną, nie domyślną interpretacją.
6. Uzgodnij sumy/unikalność raw → curated, a potem snapshot + replay → stan docelowy. Profile fault injection w raw nie mogą psuć canonical seed API.

## 3. Topics, envelope i kompatybilność

Proponowana decyzja **ADR-09** zachowuje legacy v1 oraz oddziela bogate wyniki AI na `retailops.intelligence.v2`. Wymaga zgodnej konfiguracji topic-init, schematów i projektora. Źródłowe registry należy uzgodnić z działającym generatorem/konsumentem oraz poniższą mapą docelową. Ewentualne wpisy `retailops.orders.v1` i `retailops.ml.v1` trzeba rozstrzygnąć jawnie, aby nie utrzymywać sprzecznych standardów.

| Topic docelowy | Event types | Obsługa |
|---|---|---|
| `retailops.sales.v1` | `order_created`, `sale_completed`, `return_completed` | Fakty źródłowe; zgodne legacy payloady. |
| `retailops.inventory.v1` | `stock_changed`, `inventory_snapshot_recorded`, `replenishment_completed` | Wersjonowane stany/ruchy, właściwa lokalizacja. |
| `retailops.pricing.v1` | `price_changed`, `promotion_started`, `promotion_ended` | Czas obowiązywania i dostępności. |
| `retailops.operations.v1` | `alert_created`, `workflow_action_performed` | Kontekst i outcome feedback, bez wykonywania workflow przez agenta. |
| `retailops.intelligence.v1` | Legacy `forecast_generated`, `anomaly_detected` | Dotychczasowe demo bez zmiany znaczenia pól. |
| `retailops.intelligence.v2` | AI `forecast_generated`, `anomaly_detected`, `stockout_risk_scored`, `recommendation_generated` | Nowy projektor i jawne schematy bogatych wyników. |
| `retailops.dlq.v1` | Uzgodniona koperta dead-letter | Odsyłacz do trwałego raw, powód i retry status; kontrola dostępu. |

Przykład kompletnego envelope źródła:

```json
{
  "event_id": "11111111-1111-4111-8111-111111111111",
  "event_type": "sale_completed",
  "schema_version": "1.0",
  "topic": "retailops.sales.v1",
  "source": "retailops.synthetic-generator",
  "correlation_id": "sale-order-42",
  "occurred_at": "2026-04-03T10:15:30Z",
  "ingested_at": "2026-04-03T10:15:31Z",
  "payload": {}
}
```

`payload: {}` powyżej jest tylko miejscem na payload w ilustracji envelope; kompletne zdarzenie musi przejść własny JSON Schema `sale_completed` i pusty payload należy odrzucić. Envelope AI ma te same nazwy pól, `schema_version: "2.0"`, `topic: "retailops.intelligence.v2"`, `source: "retailops-ai"` i payload z tabeli niżej. `occurred_at` to czas powstania wyniku, a jego forecast origin/as-of pozostaje osobnym polem payloadu.

Walidacja wiąże transportowy topic z deklarowanym `topic`, event type, major version i schema payloadu. Obsługiwane minor versions są wyliczone w registry; nie stosuj polityki „dowolny przyszły numer”. Tolerancja dla opcjonalnych dodatkowych pól jest testowana osobno. Nowy typ na `.v1` nie jest automatycznie kompatybilny z zamkniętą listą istniejącego konsumenta. Nieobsługiwane typy/version trafiają do kwarantanny/DLQ, nie do no-op success.

### Payload wyników AI v2

| Event | Wymagany payload / źródło schematu |
|---|---|
| `forecast_generated` | Utrwalony forecast zgodny z ML API: ID, target type `observed_sales_units`, origin/as-of, target date/horizon, product/location/store/channel, units i jednostka, opcjonalny poprawnie skalibrowany przedział, model version, dataset/feature/run/release lineage, freshness. |
| `anomaly_detected` | Zgodny z ML API wynik: ID, observation window i cutoff, grain, observed/expected values, score/severity, detector/threshold versions, explanation codes i source refs. Skala starego `deviation_percent` nie jest automatycznie skalą nowego score. |
| `stockout_risk_scored` | Zgodny z ML API wynik: ID, as-of/horizon, poprawna lokalizacja, probability, risk band, model/calibration/threshold versions, inventory freshness i run/feature lineage. |
| `recommendation_generated` | Struktura sugestii z sekcji 7, w tym ID, policy/agent versions, evidence refs, expiry i `requires_human_review=true`. |

Dokładne pole i nullability forecast/anomaly/risk są współdzielone z wersjonowanym schematem z [ML API](ml-api-lifecycle.md), nie utrzymywane ręcznie w dwóch modelach. Publikacja zachodzi po trwałym zapisie wyniku. `event_id` i tożsamość wyniku są stabilne przy retry. `partition_key` deterministycznie grupuje ten sam grain; to porządek w obrębie partycji, nie globalny zegar biznesowy.

RetailOps projektuje te dane do własnych nowych/rozszerzonych read models. Legacy forecast może otrzymać świadomie wyliczoną agregację okresową z określoną jednostką i lineage, ale nie traci się oryginalnego store/channel. Heurystyczny `/inventory-risks` i modelowe AI probability są prezentowane oddzielnie. Wskaźnik „najnowszy” porównuje zatwierdzony model release, właściwy as-of i run policy, a nie tylko czas dostarczenia eventu. Historia wcześniejszych wyników pozostaje odczytywalna.

### Trwałość, ACK i DLQ

Transakcja konsumenta zapisuje inbox dedup, skutki domenowe/projekcję, processed outcome/checkpoint i outbox. ACK następuje wyłącznie po trwałym przetworzeniu albo trwałej kwarantannie nieprzetwarzalnego rekordu. Kafka commit wskazuje następny offset do czytania i nie może przeskoczyć nieprzetworzonej luki danej partycji. Wymagana jest kontrola współbieżności i fencing podczas rebalance, aby stary worker nie zatwierdzał checkpointów nowego właściciela.

Invalid JSON nie ma wiarygodnego `event_id`: kwarantanna identyfikuje go przez transportowy topic/partition/offset i hash surowych bajtów. Zachowaj raw bez wypisywania potencjalnych sekretów w logach; metadane DLQ przechowują reason code/schema version, trace, czas i ref do raw. Trwały DLQ outbox może czekać na broker; ACK jest dopuszczalne dopiero po jego zatwierdzonym zapisie. Jeśli nie działa również trwała kwarantanna, nie ACK-uj. Wznowienie i replay DLQ wymagają jawnej decyzji operatora i zachowania original identity.

Gwarancja docelowa to at-least-once transport i jeden efekt biznesowy dzięki idempotencji. Nie deklaruj „exactly once” wyłącznie dlatego, że istnieje unique `event_id`.

## 4. Corpus/index contract

Każdy dokument: `document_id`, `repository`, `commit_sha`, `path`, `title`, `document_type`, `access_class`, `document_status`, `content_checksum`; dla statusu `verified` także `verification_ref`, `verified_commit`, `verified_at`. Chunk dodaje `chunk_id`, `heading_path`, `chunk_index`, `content_checksum`, `token_estimate`, `chunker_version`. Citation binding wiąże content identity z konkretną rewizją dokumentu. Nie wolno zwracać nowego commitu z treścią pochodzącą ze starego bez sprawdzenia checksum.

`document_status`: `specified` (plan), `implemented` (kod wskazany), `verified` (odtwarzalny dowód), `deprecated`, `historical`. Pytanie o stan wdrożenia wymaga kodu/evidence adekwatnego do commitu; `specified` nie może być źródłem stwierdzenia „działa”. Korpus obejmuje approved dokumenty obu repozytoriów, cards, runbooki i kontrakty; wyklucza raw transakcje, truth, sekrety, logi, prywatne uploady i przypadkowe internetowe treści.

`corpus_manifest` przypina allowlist/config i zatwierdzone SHA/checksums. `chunk_manifest` mapuje dokumenty na fragmenty. `index_manifest` przypina: `index_id`, corpus/chunk IDs, embedding provider/model/config/dimension, distance/normalization, retrieval version, schema/migration version, środowisko/access policy, counts/checksums i report IDs. `indexed_at` i czasy wykonania nie zmieniają content identity. Embedding cache ma klucz content hash + embedding configuration, nie sam tekst/ID dokumentu.

Nie mieszaj wektorów o innych wymiarach/modelach. Nowa konfiguracja tworzy candidate index; pełny build i ewaluacja poprzedzają atomową aktywację. Jeden request przypina jeden aktywny `index_id`. W przypadku awarii zachowaj poprzedni aktywny manifest i sprawny rollback. Usunięte/wycofane źródła nie są dostępne w nowym indeksie; wymaganie pilnego odebrania dostępu stosuje nadrzędny deny filter również do starych wersji/cache.

Golden set obejmuje 30–50 przypadków z expected sections, forbidden sources, answerability, doc status, scope, expected/forbidden tools i dopuszczalnym outcome. Przed testem zamroź progi dla recall@k/MRR, citation correctness, groundedness i latency/cost. Krytyczne przypadki auth, sekretów, zakazanych writes i wymiaru/wejścia indeksu muszą przechodzić w 100%; ich failure blokuje release. Wyniki fake embeddings nie są dowodem jakości semantycznej. Raport real embeddings i test Bedrock ma oddzielne oznaczenie.

## 5. Narzędzia, tożsamość i budżet agenta

| Narzędzie | Źródło i istotne ograniczenie |
|---|---|
| `get_sales_summary` | Typowany RetailOps adapter/approved snapshot; ograniczony okres i grain, agregaty bez danych klienta; bez sklepu w źródle nie deklaruje filtrowania sklepu. |
| `get_inventory_status` | RetailOps API; jawne warehouse→location mapping, unit, available/as-of i freshness. |
| `get_demand_forecast` | Utrwalony approved wynik AI; observed sales target, origin, model/release, przedział i ograniczenia stockout censoring. |
| `get_stockout_risk` | Utrwalone calibrated probability dla grain/horizon; model/threshold/inventory freshness; nie legacy heurystyka. |
| `get_detected_anomalies` | Bounded lista AI z observation window, detector version, expected/observed i źródłem. |
| `get_live_operations` | RetailOps read model; kondycja strumienia i świeżość, nie dowód zapisania konkretnej prognozy. |
| `get_model_status` | Metadata/MLflow tylko read: wersja wdrożona, aliasy, evaluation, drift i lineage. |
| `search_knowledge` | Jeden przypięty pgvector index, access/status filters przed outputem, źródła z allowlisty. |

Każde narzędzie ma input/output Pydantic/JSON Schema, timeout, max period/rows, redaction, telemetry i deterministic fake. Output: `tool`, `status`, `as_of`, `freshness_status`, `source_ref`, `items` lub typowany obiekt; error zawiera stabilny `code`, `retryable` i bezpieczny opis. Wspólne klasy błędów: `invalid_scope`, `unauthorized`, `unavailable`, `stale`, `not_found`, `unsupported_grain`, `budget_exceeded`. Brak danych nie jest zerem sprzedaży. Dane z narzędzia nie są instrukcjami.

Principal pochodzi z serwera. Local demo: osobne poświadczenia usługowe/operatora i jawna mapa dozwolonego scope poza repo. AWS/dev: workload identity dla AWS i zweryfikowana tożsamość aplikacji lub zamknięty dostęp usługowy. Obecny RetailOps `user_id`/demo role nie jest loginem, JWT ani izolacją tenantów. Gdy dodajesz OIDC, weryfikuj signature/issuer/audience/expiry; nie deklaruj tej funkcji bez wdrożenia.

| Rola | Uprawnienia docelowe |
|---|---|
| `viewer` | Autoryzowany odczyt wyników ML, model status i drift. |
| `operator` | Odczyty viewer oraz bounded assistant query i własne odpowiedzi/trace. |
| `pipeline` | Zlecanie/persistowanie dozwolonych runów ML i publikowanie trwałych wyników; nie dowolny indexing ani workflow. |
| `admin` | Administracja zatwierdzonymi index runs i bezpieczne metadane zgodnie z audit policy; prawa operatora tylko jeśli nadane. |
| `promoter` | Kontrolowany release/promotion przez CLI/CI; rola niedostępna dla LLM. |

Requested scope jest walidowane względem uprawnień principal. Jeśli zawiera nieautoryzowaną jednostkę, odpowiedź to 403 zamiast milczącego rozszerzenia zakresu. Niepodany scope oznacza tylko skonfigurowany ograniczony default principal, nigdy „wszystko”. Role, principal IDs i tenant nie są polami wybieranymi przez LLM. Listy, pojedyncze rekordy, conversation/trace i cache podlegają temu samemu sprawdzeniu.

Domyślny profil `agent-bounded-v1` (nowa konfiguracja do zapisania w repo): pytanie do 2000 znaków; okres do 90 dni; do 20 produktów i 5 sklepów; top-k 5, kontekst dokumentowy do 6000 tokenów; maksymalnie 6 tool calls łącznie, 1 dogranie brakującego dowodu i 1 repair; deadline całego requestu 45 s, timeout pojedynczego tool 5 s; łączny budżet wywołań modelu 12 000 input i 1500 output tokens; do 2 retry tylko w pozostałym budżecie; 2 równoległe runy principal. Tools zwracają domyślnie do 20 i maksymalnie 50 rekordów. Limity są walidowane przed wykonaniem, można je zaostrzyć środowiskowo. Limit kosztu per run i per smoke jest wymaganym polem konfiguracji wyliczanym dla wybranego modelu; nie zakładaj stałego cennika. Po przekroczeniu budżetu nie rozpoczynaj nowego kroku.

Read-only dotyczy źródłowych operacji biznesowych. System może zapisać własną odpowiedź, bezpieczny trace i sugestię, ale agent nie ma ogólnego narzędzia zapisu i nie inicjuje samodzielnie zadań administracyjnych ani harmonogramów operacyjnych.

## 6. Assistant API — dokładny kontrakt MVP

`POST /api/v1/assistant/queries` jest synchroniczne i ograniczone powyższym profilem. Rola `operator`; wymagane authentication i correlation. `question` jest niepuste, `scope.from <= scope.to`; `conversation_id`, jeśli podany, musi należeć do tego principal/scope. Na pierwsze MVP można wymagać `conversation_id: null`; nie przechowuj nieizolowanej pamięci między użytkownikami. Identyfikatory produktów/sklepów to prawidłowe identyfikatory źródła, walidowane resolverem, a nie swobodnie wymyślane etykiety.

```json
{
  "question": "Co może wyjaśniać spadek sprzedaży i co należy sprawdzić?",
  "scope": {
    "product_ids": ["22222222-2222-4222-8222-222222222222"],
    "store_ids": ["33333333-3333-4333-8333-333333333333"],
    "from": "2026-04-01",
    "to": "2026-04-07"
  },
  "conversation_id": null
}
```

Schemat sukcesu obejmuje wszystkie pola poniżej. `outcome` ma wartości `answered`, `insufficient_evidence`, `refused`; `confidence` jest oceną jakości dowodów `low|medium|high`, nie kalibrowanym prawdopodobieństwem prawdziwości. Każda liczba biznesowa i wniosek mają dowód; cytaty do dokumentów nie zastępują bieżących danych liczbowych.

```json
{
  "answer_id": "44444444-4444-4444-8444-444444444444",
  "outcome": "insufficient_evidence",
  "summary": "Nie ma wystarczających danych, aby ustalić przyczynę spadku sprzedaży.",
  "evidence": [],
  "recommended_actions": [],
  "confidence": "low",
  "data_freshness": {
    "sales": {"as_of": null, "status": "missing"},
    "inventory": {"as_of": null, "status": "not_requested"},
    "predictions": {"as_of": null, "status": "not_requested"}
  },
  "citations": [],
  "limitations": ["Brak wystarczających obserwacji dla wskazanego sklepu i okresu."],
  "trace_id": "55555555-5555-4555-8555-555555555555",
  "agent_config_version": "retail-analyst-v1",
  "index_id": "index-example-v1",
  "created_at": "2026-04-08T08:00:00Z"
}
```

`evidence[]`: wymagane `claim`, `source_type` (`tool|document|calculation`), `source_ref`, `as_of` (null dla dokumentu) i `supporting_refs` (lista, również pusta). `calculation` wymaga dodatkowo `calculation_id` wskazującego zatwierdzony deterministyczny wzór i źródłowe operands; swobodnie wyliczona liczba LLM nie przechodzi walidacji. `citations[]`: `repository`, `commit_sha`, `path`, `heading`, `chunk_id`, `document_status`, `source_ref`. Cytat musi należeć do pobranego zbioru tej wersji indeksu. `data_freshness` dla każdej użytej domeny: `as_of` i `status=current|stale|missing|unavailable|not_requested`; progi current/stale pochodzą z wersjonowanej polityki domeny, nie oceny LLM.

`recommended_actions[]` zawiera `recommendation_id`, `action`, `priority=low|medium|high`, `rationale`, `evidence_refs`, `requires_human_review=true`; persisted pełny obiekt jest opisany w sekcji 7. Dla `insufficient_evidence` dopuszczalne są jedynie sugestie uzupełnienia/odświeżenia danych, bez wymyślonych operacyjnych ilości. Dla `refused` nie występują operacyjne akcje. Jeżeli potrzebna informacja istnieje w niedostępnej zależności, użyj błędu 424 zamiast pozorowania, że nie ma jej w danych.

| Status HTTP | Znaczenie |
|---|---|
| `200` | Poprawna strukturalnie odpowiedź, kontrolowany brak dowodów lub odmowa; obowiązkowy `outcome`. |
| `401` / `403` | Brak poprawnej tożsamości / brak uprawnień do zakresu lub operacji. |
| `422` | Nieprawidłowe pytanie/scope, zbyt długi okres lub nieobsługiwane ziarno żądania. |
| `424` | Wymagane narzędzie danych lub evidence source niedostępne. |
| `429` | Admission rate/concurrency/token/cost limit; bez rozpoczynania kolejnego runu. |
| `502` | Provider zwrócił niewalidowalną odpowiedź mimo jednej dozwolonej naprawy. |
| `503` | Bedrock niedostępny lub circuit breaker otwarty. |
| `504` | Przekroczony deadline całego wykonania. |

Wszystkie błędy stosują wspólny problem-details envelope z ML API (`type`, `title`, `status`, `detail`, `instance`, `correlation_id`, opcjonalne bezpieczne field errors). Nie zawierają stack trace, surowego promptu, sekretów ani wewnętrznych ścieżek. Dla przykładu 424 `type` wskazuje `dependency-unavailable`, `detail` nazywa klasę źródła, a nie poświadczenia/host z danymi wrażliwymi. Pomyłkę wewnętrzną niepasującą do powyższych mapuj na bezpieczne 500 i trace.

`GET /api/v1/assistant/runs/{trace_id}`: właściciel lub uprawniony administrator; 200 z `trace_id`, `answer_id` (nullable), `status=running|succeeded|failed`, `outcome` (nullable), `requested_at`, `completed_at` (nullable), `agent_config_version`, `index_id`, `nodes[]` (`name`, `status`, `duration_ms`, `error_code` nullable), `tools[]` (`name`, `status`, `source_refs`, `freshness_status`), `usage` (`input_tokens`, `output_tokens`, `duration_ms`, `estimated_cost`, `currency`), `error_code` nullable. Brak zasobu lub brak prawa do cudzego trace zwraca 404, aby nie ujawniać istnienia. Nie zwracaj chain-of-thought ani pełnych prywatnych tool payloadów.

Feedback `POST /api/v1/assistant/answers/{answer_id}/feedback` pozostaje rozszerzeniem po podstawowym odbiorze: wersjonowany `helpful`, reason codes i komentarz, uprawnienia właściciela, brak automatycznego online learning. Nie jest wymagany do pierwszego działającego agenta.

## 7. Sugestie i rekomendacje

Odczyt `GET /api/v1/recommendations` oraz `GET /api/v1/recommendations/{recommendation_id}` jest częścią wspólnego API ML. Pełny persisted item:

- `recommendation_id`, `created_at`, `expires_at`, `origin="retailops-ai"`;
- `product_id`, `store_id`/`stock_location_id`, `channel` zgodnie z jawnym scope; nullable wyłącznie gdy akcja dotyczy szerszego zatwierdzonego zakresu;
- `recommendation_type` z zamkniętej wersjonowanej listy, początkowo `review_replenishment`, `investigate_anomaly`, `refresh_source_data`;
- `action`, `priority`, `summary`, `rationale`, `evidence_refs` (niepuste dla sugestii operacyjnej);
- `policy_version`, `agent_config_version`, `trace_id`, `model_release_refs`, `source_as_of`, `freshness_status`;
- `requires_human_review: true`, `status="proposed"` przy utworzeniu.

Polityka kwalifikuje sugestię, np. wysokie calibrated stockout probability + current inventory + zatwierdzony model/forecast bez failed quality gate → `review_replenishment`. LLM objaśnia przesłanki; nie tworzy własnego progu, przyczyny ani zamawianej ilości. Identyczna sugestia z retry tego samego answer/run ma tę samą identity. Wygaśnięcie, stale evidence albo nowy model release wymaga ponownej oceny, nie cichego ponownego wykonania.

Nie istnieje endpoint „execute recommendation”. Agent nie akceptuje sugestii, nie tworzy purchase order i nie zmienia źródłowego workflow. Jeśli człowiek wykona działanie przez dotychczasowy workflow RetailOps, tożsamość/autoryzacja/audit tej akcji należą do RetailOps; event może wrócić jako późniejszy feedback. `recommendation_generated` publikuje tylko trwałą sugestię do odczytu, nie polecenie operacyjne.

## 8. Administracja RAG — dokładny kontrakt MVP

`POST /api/v1/knowledge-index-runs`: tylko `admin`/jawnie uprawniona usługa indeksująca; wymagane `Idempotency-Key`. Request:

```json
{
  "corpus_config_id": "approved-retailops-docs-v1",
  "sources": [
    {
      "repository": "Oskar-Stachowski/retailops-cloud-native-platform",
      "commit_sha": "0000000000000000000000000000000000000000"
    }
  ],
  "index_config_id": "rag-pgvector-v1",
  "evaluation_set_id": "rag-golden-v1"
}
```

Zerowe SHA jest wyłącznie placeholderem przykładu; rzeczywiste żądanie musi wskazać istniejący commit. Pola wskazują wyłącznie istniejące zatwierdzone konfiguracje i pełne SHA. Nie przyjmuj dowolnych URL/path, tekstu promptu ani zmiany modelu/rozmiaru embeddings z żądania. `sources` musi odpowiadać wymaganym repozytoriom zatwierdzonej corpus config; powyższy przykład pokazuje konfigurację jednego repozytorium, produkcyjny korpus obejmuje także przypięte AI repo. Server validation odrzuca brak wymaganej pozycji.

Odpowiedź `202` jest wspólnym trwałym Run z `run_type="knowledge_index"`, `status="queued"`, immutable request hash i `Location: /api/v1/knowledge-index-runs/{run_id}`. Walidacja/auth następuje przed zapisaniem runu. Powtórzony ten sam klucz + request zwraca ten sam run; inny request pod kluczem → 409. Job zapisuje candidate index i raport, nie przełącza aktywnego indeksu. `succeeded` oznacza ukończoną budowę i wymagane kontrole, nie aktywację.

`GET /api/v1/knowledge-index-runs/{run_id}`: administrator/uprawniona usługa; wspólny Run z `output_ref` po sukcesie: `index_id`, `manifest_ref`, `evaluation_report_ref`, `activation_status="candidate"`. Błędy bezpiecznie wyjaśniają niedozwolone źródło, mismatch checksum/dimension, brak pliku lub failed gate. Statusy `queued|running|succeeded|failed|cancelled` zgodne ze wspólnym kontraktem; rezygnacja z joba nie zmienia aktywnego indeksu.

`GET /api/v1/knowledge-indexes/current`: administrator/uprawniona usługa; 200:

```json
{
  "index_id": "index-approved-example-v1",
  "status": "active",
  "manifest_ref": "artifact:index-approved-example-v1/manifest",
  "corpus_manifest_id": "corpus-example-v1",
  "chunk_manifest_id": "chunks-example-v1",
  "index_config_id": "rag-pgvector-v1",
  "embedding_config_id": "bedrock-embedding-approved-v1",
  "embedding_dimension": 1024,
  "document_count": 42,
  "chunk_count": 210,
  "activated_at": "2026-04-08T07:00:00Z",
  "evaluation_report_ref": "evaluation:rag-example-v1"
}
```

Liczby/IDs/wymiar w przykładzie są ilustracyjne; rzeczywisty wymiar musi zgadzać się z zatwierdzoną konfiguracją modelu i bazą. Przed pierwszą aktywacją endpoint zwraca 404 z `index-not-configured`. Wymiana aktywnego indeksu to kontrolowany CLI/CI po bramkach i ze wskazaniem immutable index ID; brak publicznego HTTP activation i brak takiego narzędzia agenta. Server-side agent może korzystać z wewnętrznego resolvera aktywnego indeksu bez nadawania operatorowi roli admin.

## 9. Wersja release i odbiór

Agent release spina: graph version + prompt checksums + tool schemas + retrieval config + corpus/index IDs + embedding model/dimension + chat model/inference profile/region + response schema + policy/budget config + golden evaluation version. Zmiana dowolnego składnika wymaga właściwej ewaluacji; release manifest zawiera raport oraz wynik wymaganych gates. Alias `current` jest rozwiązywany do niezmiennego indeksu na początku runu.

Evidence hierarchia: aktualny typed tool → adekwatny wersjonowany kontrakt/model card → runbook/polityka → ogólna wiedza tylko do niewiążącego objaśnienia. Dokument nie nadpisuje bieżących danych, a LLM nie rozstrzyga sam konfliktu autoryzacji. Numeric faithfulness, citation coverage, odmowy i ograniczenia kosztowe są mierzone na golden set; LLM-as-judge tylko uzupełnia sprawdzalne testy.

Bezpieczna telemetry przechowuje wersje, statusy, latency, tokens i estimated cost bez raw pytania/danych w etykietach metryk; trace redaguje dane wrażliwe i ma ograniczoną retencję. Cache zawiera principal/scope, release/index IDs, request hash oraz granicę freshness. Classical ML pozostaje dostępne przy awarii LLM. Stan `blocked` rzeczywistego Bedrock testu jest raportowany wprost i nie może zostać zamieniony na sukces na podstawie stubu.

## 10. Rozszerzenia pozostawione poza pierwszym odbiorem

Pierwotna specyfikacja dopuszczała dodatkowo hybrid search/FTS/RRF i reranking, HNSW po pomiarze skali, Bedrock Guardrails po ewaluacji, semantic response cache z zachowaniem scope/freshness, feedback, model routing oraz Langfuse/zarządzaną platformę trace. Zachowujemy je jako opcjonalny backlog po pomiarze korzyści i kosztu. Osobny vector database wymaga wykazania ograniczeń pgvector. Future human-in-the-loop dla narzędzi piszących jest odrębną zmianą zakresu i threat modelu; nie należy do read-only agenta ani obecnych kryteriów odbioru.
