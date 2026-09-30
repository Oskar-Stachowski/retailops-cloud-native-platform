# 07. Dodaj anomalie, błędy danych i detekcję

**Status: plan wdrożenia. Repo: RetailOps + AI. Zależności: 04, 05, 06.**

Lokalne przygotowanie upstream rozpoczęto od [07.1a — trzech scenariuszy popytu](../../../reference/business-anomaly-scenarios.md).
Kandydat ma oddzielną truth i pełne odtworzenie procesu, ale nie jest nowym
snapshotem ani odbiorem AI 07. Return spike i inventory-censored episode,
raw DQ, handoff oraz downstream pozostają dalszym zakresem.

Cel: uzyskać oddzielne, deterministyczne scenariusze business anomalies i raw data faults, a następnie porównać seasonal-residual baseline z Isolation Forest w istniejącym lifecycle MLflow. Offline replay/curation jest częścią07. Produkcyjna trwałość brokera, ACK/DLQ i projekcje są etapem10; nie deklarować ich zaliczenia na podstawie fixture offline.

Normatywne źródła: [dane i czas](../kontrakty/dane-i-czas.md), [profile i bramki](../kontrakty/profile-i-bramki.md), [ML/API lifecycle](../kontrakty/ml-api-lifecycle.md), [integracja](../kontrakty/integracja-agent.md), evidence04–06. Forecast wykorzystany jako expected value musi być ponownie oceniony dla snapshotu po06.

## Kolejność małych PR-ów

1. **RetailOps — scenariusze business anomalies.** Wersjonowany injection contract i osobny `anomaly_injections` artifact: ID, typ, product/location/channel scope, start/end, magnitude/shape, affected fields, seed, generator version. Wymagane one-day spike, multi-day spike, sustained drop, return spike i inventory-censored episode. Modyfikować proces przed finalnym wygenerowaniem faktów (demand, returns lub rzeczywiste ograniczenie dostaw/zapasu), nie sam label. Dopisać clean control windows, neutralne promotion/seasonality controls i insufficient-history cases. Overlapping injections mają jawny deterministic composition albo są odrzucane. Legacy anomalies/alerts pozostają precomputed outputs.
2. **RetailOps — realne DQ faults.** Osobno generować exact duplicate event ID, business duplicate z innym envelope ID, late event, out-of-order, missing optional context, unsupported major i nieobsługiwany minor/additive field według polityki kontraktu. Faults dotykają raw replay, nie poprawnych kanonicznych CSV/Parquet do seedowania. `data_quality_injections` ma event/raw reference, issue type, expected action, seed i timing. Etykiety injekcji nie są polem normalnego event payloadu.
3. **Granica offline replay/curation.** Wykorzystać odebrany w OPS-07 wykonywalny envelope/payload schema legacy v1 i uzgodnić rozszerzenia z kontraktami01/10. Bounded fixture reader testuje dedup po event ID i business key, late-arrival handling, quarantine/DLQ fixture, immutable revisions, aggregate reconciliation i watermark. Zapisuje raw/accepted/duplicate/late/quarantine/DLQ counts oraz rozliczenie każdej injekcji. Nie dodawać nowych topiców lub event types do starego konsumenta bez osobnej kompatybilnej zmiany10.
4. **Nowy snapshot i anomaly dataset.** Ponowić03 dla zmienionych scenariuszy. AI tworzy observed value, historical expected value, residual, robust scale, contextual price/promo/inventory/DQ fields i insufficient-history flag. Użyć jawnej allowlist. Label dla ocenianego okna dołącza wyłącznie evaluator z truth; model nigdy go nie dostaje. OOF/rolling-origin expected i scale są dopasowane przed ocenianym outcome. Jeśli zmienił się source/forecast schema lub scenariusze, ponowić właściwe04/05 przed generacją downstream features.
5. **Reguły i seasonal residual baseline.** Warstwa DQ najpierw oznacza niekompletne/niewiarygodne wejście. Baseline porównuje observed z seasonal naive lub historycznym forecastem, normalizuje resztę robust scale i stosuje progi wybrane na validation. MAD/scale=0 ma jawną bezpieczną politykę, nie dzielenie przez zero. Status insufficient_data oznacza brak score/uzasadnienie. Spodziewana promocja nie jest automatycznie anomaly; błędy danych nie są automatycznie biznesowym spadkiem sprzedaży.
6. **Isolation Forest candidate.** Dopasować pipeline preprocessingu+IF na dozwolonych historycznych obserwacjach training. Domyślny detector nie dostaje oracle clean labels ani parametrów injekcji. Ewentualny wariant trenowany na label-assisted clean subset oznaczyć jako dodatkową ablation, nie jako uczciwy bezetykietowy baseline. Contamination, features i score threshold wybierać wyłącznie train/validation; końcowy test pozostaje nietknięty.
7. **MLflow, batch i wynik.** Użyć lifecycle05: experiment/run/model artifacts, manifest IDs, cutoff/splits/config, metrics, model card, candidate registration i kontrolowana promocja. Batch scoring ładuje rzeczywisty zatwierdzony artifact albo jawny baseline; nie zastępuje IF cichym heurystycznym kodem. Wynik zawiera model/version, scoring window, observed/expected/residual, anomaly score, severity, reason codes, quality/freshness, status i lineage. API jest read-only; side effects i projekcje realizuje później10.

## Protokół ewaluacji anomalii

Rozdzielić business label od DQ injection label. Wierszowy classifier/detector nie musi „wykrywać” wszystkich błędów schematu — to zadanie DQ layer. Raport ocenia osobno prawidłową akcję pipeline i modelowy alert.

Zamrozić przed testem dwa poziomy metryk:

- **Observation level:** precision, recall, false alerts/1000 ważnych obserwacji, wyniki per typ/segment, high-severity precision i udział insufficient_data. Mianownik clean observations wyklucza nieocenialne okna według jawnej polityki, ale raportuje ich liczbę.
- **Episode level:** epizod jest wykryty przez pierwszy alert zgodny co do scope w jego oknie. Domyślna tolerancja to zero wyprzedzenia i maksymalnie jedna doba po końcu epizodu; liczyć również delay od startu i od dostępności pierwszego dowodu. Wersjonowana polityka może ją zmienić przed testem. Kolejne alerty tego samego epizodu nie podbijają recall; raportować repeat-alert count. Alert może dopasować najwyżej jeden epizod przy zdefiniowanej regule overlap.

Brak pozytywów daje recall/PR-AUC=`not_evaluable`; brak dodatnich predykcji nie daje automatycznie precision=1. Jednodniowy spike wykryty po zamknięciu doby nie oznacza realtime detection. Progi severity i limit alertów wybiera się na validation; normalizacja i expected value nie wykorzystują ocenianego punktu do fitu. Finalne trzy seedy i scenariusze są zgodne z profile policy.

Wyjaśnienie mówi o zaobserwowanych faktach, np. `below_expected_range`, `inventory_constraint_present`, `data_quality_suspicion`. Nie dowodzi przyczyny ani intencji. Dodatkowy prompt/agent nie zmienia decyzji ewaluacyjnej detektora.

## Kontrole wymagane i negatywne

- Ten sam seed daje te same injekcje i observable effects; zmiana labelu bez zmiany procesu jest wykrywana. Każdy business type ma epizody i clean controls oraz porównywalne okna expected/observed.
- Truth/label/magnitude/seed injekcji nie może trafić do features ani runtime. Fit expected model/scale na ocenianym outcome lub przyszłych rekordach powoduje leakage failure.
- Same raw replay uruchomione dwa razy nie zmienia poprawnego agregatu ani nie dubluje uznanych działań. Exact i business duplicates są rozróżnione.
- Late/out-of-order data tworzą właściwą wersję agregatu, nie nadpisują historycznej wiedzy. Missing optional context zachowuje dozwoloną semantykę; invalid major trafia do jawnej kwarantanny/DLQ fixture, nie jest „naprawiany” arbitralnie.
- Source facts pozostają zgodne z commerce i ledger gates mimo raw faults. Każda DQ injection ma expected vs observed pipeline action i pełną reconciliation.
- Normal seasonality/promotion, zero-sale/no-demand, inventory censoring i true business spike mają oddzielne fixtures; cold start nie udaje normalnego wyniku0.
- IF artifact przechodzi zapis/odczyt i daje zgodne batch predictions, wraz z dataset/model lineage. Promotion blokuje brak metryk/próbek/threshold policy.
- Testy transportowe DB down/crash before ACK/DLQ failure są obowiązkowe w10; wynik07 ma status offline-only dla durability.

## Artefakty i Definition of Done

Injection schemas/config, labels poza facts, raw faults fixtures, offline curation report, nowy immutable snapshot, anomaly feature/label/split manifests, baseline i IF artifacts, MLflow runs, model/evaluation cards oraz przykładowe API responses. Raport podaje per-observation i per-episode wyniki oraz ograniczenia liczebności/częstotliwości.

Etap jest zakończony, gdy injekcje i DQ actions są rozliczone, oba detektory porównano bez leakage, a zwycięski baseline/candidate jest odtwarzalny i gotowy do read-only serving. IF nie musi wygrać; jawnie zaakceptowany baseline pozostaje champion, jeśli candidate nie przechodzi gates. Integracja transportowa oraz prezentacja wyników w RetailOps czekają na10.

## Prompt dla Codex

```text
Wykonaj etap07 z etapy/07-anomalie-dq.md w osobnych PR-ach RetailOps i AI.
Przeczytaj README.md, architektura.md, kontrakty/dane-i-czas.md,
kontrakty/profile-i-bramki.md, kontrakty/ml-api-lifecycle.md,
kontrakty/integracja-agent.md oraz evidence04/05/06.
Upstream wdrażaj business injections do procesu, DQ faults tylko do raw replay,
truth labels oddzielnie i bounded offline curation z reconciliation/dedup.
Opublikuj nowy snapshot03. Downstream przygotuj PIT-safe expected/residual features,
seasonal-residual baseline i Isolation Forest, z MLflow lifecycle05.
Nie używaj detector output jako własnej etykiety ani future outcomes do normalizacji.
Zamroź observation/episode metrics, alert dedup i thresholds przed final testem.
Przetestuj required negative cases, zapisz lineage/model cards/evidence.
Nie ogłaszaj gotowej broker durability/ACK/DLQ ani integracji RetailOps read models:
to odbiór etapu10. Nie wykonuj automatycznych działań biznesowych ani deploy cloud.
```
