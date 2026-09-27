# Szablony dokumentacji i dowodów

Wypełniaj rzeczywistymi wartościami. Brak wyniku oznacz `not_run`, `blocked` lub `not_evaluable`, nigdy przykładową liczbą udającą pomiar. Długie raporty/artefakty przechowuj poza Git z manifestem i checksums; w Git mały zanonimizowany opis.

## 1. Rejestr etapu / PR

```yaml
stage_id: "00"
status: planned
repository: ""
source_commit: ""
implementation_commit: ""
started_at: null
verified_at: null
scope: []
dependencies: []
changed_contracts: []
checks: [] # name, command, expected, observed, status, artifact_ref
decisions: []
limitations: []
remaining_work: []
next_unblocked_stages: []
```

Opis PR: problem i skutek → wprowadzona zmiana → zachowanie po zmianie → kompatybilność/migracja → sprawdzone przypadki i ograniczenia. Wskaż repo zależne i kolejność wdrożenia, jeśli zmieniasz granicę integracji.

## 2. Dataset card

- Nazwa, wersja kontraktu, rola source/curated/features/labels/splits; ID i parent IDs.
- Repo/commit generatora i transformacji, effective config, seed/scenario, lock hash.
- Ziarno, klucze, pola, jednostki, waluta, lokalizacje i dopuszczalne kanały.
- Okna event time, availability, business calendar/timezone, watermark, revision policy.
- Row counts i kalendarzowa kompletność; missing vs zero vs inactive; warmup i label tail.
- Source facts, simulation truth i outputs: klasyfikacja i feature allowlist.
- Quality/realism/readiness status per zastosowanie wraz z policy version i liczebnością.
- Przetwarzanie zwrotów, cen, stockout censoring i DQ faults.
- Checksums fizycznych plików, canonical content hash i identity algorithm version.
- Lokalizacja snapshotu, retention, dozwolone zastosowania, ograniczenia syntetycznych danych.

## 3. Model card

- Nazwa zadania, target_type, grain, horizon/origin, approved input signature.
- Baseline/candidate/champion; framework, model version, training run ID i SHA.
- Dataset/feature/split IDs, preprocessing, feature allowlist, treningowy cutoff.
- Protokoły walidacji i final test, zamrożone seedy/scenariusze i konfiguracje.
- Aggregate/segment/horizon metrics, sample sizes i definicje `not_evaluable`.
- Dla forecastu: zera, bias, przedziały, stockout censoring.
- Dla anomalii: observation/episode, alert duplication, false-alert budget, delay.
- Dla stockout: eligibility, label maturity, kalibracja, progi i koszt biznesowy.
- Model/data limitations, synthetic-to-real gap, wskazania i zakazane zastosowania.
- Artifact URI/checksum, reload/inference evidence, latency/memory i środowisko.
- Zatwierdzenie, drift state, rollback reference, deployment release reference.

## 4. ML evaluation report

1. Pytanie porównania i uprzednio ustalony baseline.
2. Zamrożone config, chronologia folds, seedy i scenariusze.
3. Tożsamość danych, origin/target/availability policy oraz test braku leakage.
4. Tabela wyników baseline/candidates z liczebnościami i segmentami; te same targety i warunki.
5. Protokół tuning/calibration/threshold-selection, bez final test w strojeniach.
6. Wynik końcowego testu i niepewność/stabilność między scenariuszami.
7. Koszt pamięci/czasu, serialization/load i zgodność API output.
8. Decyzja promote/reject/insufficient_evidence i konkretne niespełnione warunki.

TensorFlow może przegrać i nadal stanowić poprawnie wykonany challenger; nie zmieniaj kryteriów po wyniku.

## 5. RAG/agent evaluation report

- Corpus manifest, approved commit/path/status/ACL, embedding/chunk/index versions.
- Golden set version, rozdzielenie development i final evaluation, pokrycie pytań.
- Retrieval recall@k, citation correctness i brak nieistniejących źródeł.
- Właściwe narzędzia, argumenty i scope; zgodność twierdzeń liczbowych z ich wynikami.
- Prompt injection, próba mutacji, brak danych, stale index, timeout/provider outage.
- Bounded loops/tool calls/tokens/cost, latency i liczba próbek.
- Model/provider/region, prompt/graph versions; fake vs live test jasno oddzielone.
- Przykłady dobrej odpowiedzi, odmowy/insufficient evidence i kontrolowanego błędu.
- Status polityk i decyzja release; brak sekretów, surowych danych klientów i ukrytego toku rozumowania w evidence.

## 6. Decyzja promocji i release

```yaml
decision_id: ""
artifact_type: model # model | agent | rag_index | application
artifact_name: ""
from_version: null
to_version: ""
decision: pending # promote | reject | pending
evaluation_ref: ""
drift_ref: ""
approved_by: ""
approved_at: null
reason: ""
rollback_ref: ""
release:
  image_digest: ""
  model_versions: {} # immutable MLflow versions, not mutable aliases
  agent_config_version: ""
  rag_index_version: ""
  feature_schema_version: ""
  chart_version: ""
  migration_version: ""
  gitops_commit: ""
```

Bootstrap pierwszego champion bez wcześniejszego modelu musi mieć jawny plan powrotu do sprawdzonego baseline albo wyłączenia scoringu przy zachowaniu read API; nie wymyślaj nieistniejącej poprzedniej wersji.

## 7. Incident i rollback evidence

- Objaw, czas, zakres i ostatni zdrowy release; alert/trace/correlation IDs.
- Źródło awarii, odtworzony test i ryzyko danych/offsetów/duplikatów.
- Działania naprawcze, konkretne przywrócone wersje i kolejność.
- Migracje i kompatybilność danych: co można cofnąć, co wymaga roll-forward.
- Kontrola po naprawie: zdrowie, konkretna predykcja, backlog/replay, brak drugiego efektu.
- Dane dojrzałe vs niedojrzałe, wpływ na monitoring jakości modelu.
- Wniosek oraz test regresyjny usuwający konkretną klasę awarii.

## 8. AWS evidence

- Wariant pokazowy, account/region (sanityzacja publicznych artefaktów), zakres i właściciel state.
- Review planu, zastosowane resource toggles, koszt założony i czas okna.
- Role OIDC/workload identity, bez sekretów i publicznej bazy.
- Co faktycznie uruchomiono; który test odróżnia cloud execution od samego planu.
- Inventory zasobów przed/po, cleanup, świadomie zachowane zasoby z powodem.
- Status kontroli kosztów; budget notification nie jest gwarancją odcięcia wydatków.
- Datowane dowody i jawne ograniczenia wariantu lokalnego z AWS.
