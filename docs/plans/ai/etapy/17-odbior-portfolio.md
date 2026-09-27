# 17 — Odbierz cały projekt i przygotuj portfolio

**Repozytoria:** RetailOps + AI. **Zależność:** 16. **Status:** instrukcja końcowego odbioru, nie deklaracja zakończenia prac.

## Cel

Zamknąć cały zakres w jednym odtwarzalnym demo i macierzy dowodów. K1 oznacza pierwszy forecasting end-to-end (00–05). K2 oznacza pełny lokalny zakres 00–15, 16A i live Bedrock smoke z 12. K3/portfolio v1 dodaje wykonany 16B i odbiór 17. Nie przenoś elementu wymaganego dla K2 do „opcjonalnych” tylko dlatego, że pierwszy forecasting już działa.

Podstawą są [architektura](../architektura.md), [profile i bramki](../kontrakty/profile-i-bramki.md), [szablony](../szablony/karty-i-evidence.md) oraz [runbook](../runbooki/operacje-i-awarie.md).

## Kolejność małych PR-ów

1. **Końcowy cross-repo audit.** Przypnij oba commity, aktualną wersję kontraktów i wykonaj clean-clone demo z zatwierdzonych artefaktów. Porównaj opis istnieje/brakuje z etapem 00 i review. Sprawdź, że stare problemy nie powróciły: PIT/location leakage, target-day features, zero metrics, tożsamość datasetów, chronologia sales/orders, ACK/DLQ, projekcja wyników i przypadkowa zmiana demo v1. Stary review opisuje wcześniejszy commit; nie aktualizuj historycznych wyników tak, jakby dotyczyły nowego kodu.
2. **Komplet wyników i ograniczeń.** Zbierz baseline/candidate/champion dla trzech zadań oraz TensorFlow challenger, nawet gdy nie wygrywa. Pokaż wspólny protokół ewaluacji, nienaruszony final test, seed/scenario robustness, segmenty, cold-start policy, censored sales oraz przypadki `not_evaluable`. Nie wybieraj tylko najlepszego seeda czy wykresu. Dane syntetyczne nie potwierdzają skuteczności w prawdziwym handlu; latent demand nie jest wejściem runtime.
3. **Evidence index i status matrix.** Każdy wiersz ma zakres, commit/config, komendę, wynik, link i ograniczenie. Stosuj `Specified`, `Implemented`, `Verified` lub `Deferred` z definicją; uruchomiona ścieżka lokalna nie oznacza wdrożenia AWS. Rozdziel statyczny przegląd i wykonane testy. Zaktualizuj karty, ADR, security/contributing policy, listę obsługiwanych wersji oraz runbook.
4. **Czytelny README i demonstracja.** Pierwszy ekran: problem biznesowy, granica RetailOps/AI, status, jedna architektura, krótka zweryfikowana ścieżka startu i linki evidence. Można przygotować około pięciu komend wysokiego poziomu, jeżeli istniejące Make targets naprawdę ukrywają wyłącznie opisane kroki. Uzupełnij CI badges, diagramy, krótkie nagranie/screenshots i znane ograniczenia. Nie zastępuj komend samym filmem.
5. **Release i powtórzenie odbioru.** Zbuduj spójny zestaw release refs, uruchom wymagane CI, clean-start smoke, failure/recovery i sprawdź cleanup. Przygotuj release notes: zakres, wersje, evidence, ograniczenia, rollback reference. Tag/publikacja następują zgodnie z autoryzacją użytkownika i wymaganiami repo; instrukcja sama nie publikuje. Odbiór uwzględnia konkretny commit, nie dawniej zielony workflow.

## Obowiązkowa macierz odbioru

| Zakres | Minimalny dowód | Gate |
|---|---|---|
| Źródło/curated | Dwa identyczne runy, canonical IDs, Parquet, manifests, quality/realism, brak truth w features | 02–03; cross-repo audit |
| Zapas/dostawy | Rekonsyliacja ledgeru, lokalizacje, jawna polityka rezerwacji (dopuszczalne reserved_qty=0), minimalny transfer fixture, zwroty, plan vs actual availability | 06 |
| Forecast | Backtest baseline/candidate, zera, PIT, bias/intervals/segments, target observed sales | 04 |
| Anomalie/DQ | Injection labels i DQ osobno, epizody/delay/false alerts, bad raw → curated | 07 |
| Stockout | Dojrzałe etykiety 7d, OOF forecast lineage, PR-AUC/calibration/top-N/cost threshold | 08 |
| TensorFlow/robustness | Ten sam protokół porównania, artefakt load/inference, z góry ustalone seeds/scenarios | 09 |
| MLflow/serving | Trzy modele, karty, wersje/checksums, audyt promocji, batch/API, reload bez zmiany wersji | 05/07/08 |
| REST/events | Kanoniczne schematy, snapshot/replay handoff, failure ACK/DLQ, idempotency/outbox, konkretny read model RetailOps | 10 |
| RAG/agent | Zatwierdzony corpus/index, retrieval golden, citations/numeric faithfulness, safe tools, fake i live Bedrock | 11–12 |
| Operacje/security | Dashboards/trace, alert+recovery, drift maturity, auth/injection/scan/SBOM | 13 |
| Kontenery/Kubernetes | Clean Compose/kind, non-root, probes, faktyczny NetworkPolicy allow/deny, resources/jobs | 14 |
| CI/GitOps | Failing required check, immutable image/model, Argo sync/drift, spójny release rollback | 15 |
| Terraform/AWS | 16A plan/security/cost, 16B actual resources/identity/runtime/ECR/S3/Bedrock oraz cleanup | 16 |
| Dokumentacja/release | Clean demo, status/evidence, ograniczenia, spójne wersje i brak sekretów/dużych danych w Git | 17 |

Bramka nie wymaga, aby candidate zawsze pokonał baseline. Wymaga poprawnej oceny, jawnej decyzji o wyborze oraz działającego zatwierdzonego modelu. Niepowodzenia jakościowe nie mogą być zamieniane w sukces przez zmianę metryki lub testowego okna po wynikach.

## Scenariusz około siedmiu minut

1. **0–1 min:** dwa repozytoria, rola systemu źródłowego i AI, architektura/status.
2. **1–2 min:** snapshot lineage oraz MLflow; baseline, scikit-learn i TensorFlow, aktualny champion i audit.
3. **2–3 min:** prognoza, anomalia i skalibrowane ryzyko dla jednego syntetycznego produktu/lokalizacji; daty, jednostki, origin i freshness.
4. **3–4 min:** pytanie o spadek sprzedaży i ryzyko stockout; narzędzia read-only, cytowania, liczby zgodne z evidence i ograniczenia.
5. **4–5 min:** Docker/Helm/CI/Argo oraz `/version` ze spójnymi refs.
6. **5–6 min:** kontrolowane stale inventory lub Bedrock outage, alert, bezpieczna odpowiedź i działające ML reads.
7. **6–7 min:** udokumentowany rollback + smoke; evidence AWS oraz inventory cleanup. Nie twórz drogiej infrastruktury na żywo tylko na potrzeby krótkiego demo.

Większe treningi, index build i cloud apply wykonaj wcześniej. Rozmowa techniczna powinna pozwolić wyjaśnić PIT, observed sales vs latent demand, calibration, immutable runtime vs aliases, granice agenta i recovery po częściowym wdrożeniu.

## Zakres opcjonalny po v1 — zachowany, ale nie blokuje odbioru

Każdą pozycję aktywuj osobnym ADR/issue po wykazaniu potrzeby; nie implementuj dla samej nazwy technologii.

| Obszar | Zachowany backlog |
|---|---|
| Bogatsza symulacja | Złożony procurement/supplier behavior ponad minimalne dostawy, optymalizacja sieci transferów i częściowego fulfillmentu klientów, cannibalization/substitution; minimalny transfer fixture i partial/delayed receipt pozostają wymagane w06 |
| Ewaluacja/dane | Rozszerzone cold-start badania, szersze seeds/scenario stress ponad obowiązkowy mały robustness set, zewnętrzny benchmark |
| Skala danych | Przyrostowe event-based snapshots ponad wymagany bounded replay, ai-load/większe profile, S3/Glue/Athena i Spark dopiero po pomiarach |
| ML serving/features | Shadow/challenger scoring, feedback/outcome loop, Feast, KServe/Seldon, dedykowany inference service, online learning/fine-tuning/GPU po osobnej potrzebie |
| Orkiestracja | Airflow/Prefect/Kubeflow/SageMaker Pipelines przy zależnościach przekraczających CLI/Jobs/CronJobs |
| Retrieval/agent | Hybrid dense+lexical/reranking, osobna vector DB gdy pgvector nie wystarczy, jeden write tool z human approval, multi-agent tylko po uzasadnieniu |
| Platforma | Canary/Argo Rollouts, managed observability/LLMOps, feature-flags service, kolejne środowiska i osobne repo GitOps |
| Cloud messaging | Wybrany transport MSK/EventBridge/SQS/inny broker po świadomej zmianie kontraktów; permanent EKS/RDS nie jest wymagany |

Podstawowe dostawy/ledger, mały zestaw seedów/scenariuszy, polityka cold-start, bounded event integration, TensorFlow i live Bedrock pozostają w wymaganym zakresie opisanym wcześniej. Nie zostały odłożone przez powyższą tabelę.

## Artefakty i Definition of Done

`docs/evidence/README.md`, komplet kart i raportów, implementation matrix, reproducible demo runbook, release manifest/notes, zwięzły README, opcjonalny film, final audit i backlog z kryteriami rozpoczęcia. Reprodukcję wykonuje się z clean clone bez ręcznego poprawiania poleceń. Każde twierdzenie ma dowód odpowiedniego rodzaju, a awaria/rollback/cleanup są wykonane, nie tylko opisane.

## Gotowy prompt do Codex

```text
Przeprowadź etap 17 jako końcowy odbiór obu repozytoriów na przypiętych commitach.
Zbuduj macierz pełnego zakresu 00–16, oddziel specified/implemented/verified/deferred
oraz static/executed/not tested. Wykaż trzy modele i TensorFlow, poprawny temporal
protokół/zera/lineage, bounded replay z projekcjami, RAG/read-only agent i live
Bedrock, monitoring/security, kind/Argo rollback oraz rzeczywisty wariant AWS i
cleanup. Powtórz clean-clone demo i najważniejsze regresje z review. Przygotuj
README, evidence index, release notes i 7-minutowy scenariusz; nie deklaruj
production-ready/zero hallucinations/cloud EKS bez dowodu. Zachowaj cały opcjonalny
backlog jako świadomie odroczony. Nie publikuj tagu ani wdrożenia poza istniejącą
autoryzacją. Podaj dokładnie, co blokuje K2 lub K3, jeśli któraś bramka nie przeszła.
```
