# Architektura, odpowiedzialność i decyzje

Proponowana architektura rozbudowy AI. Wszystkie nowe komponenty opisują stan docelowy; decyzje należy utrwalić przy wdrożeniu. Dokument nie potwierdza realizacji ani zatwierdzenia infrastruktury.

## Granice repozytoriów

| Obszar | RetailOps Cloud-Native Platform | RetailOps AI Intelligence |
|---|---|---|
| Dane | Generator, encje, zdarzenia, source quality, symulacja | Import snapshotów, curated, features, labels, split manifests |
| Prawda biznesowa | Operacyjne fakty i workflow | Predykcje i rekomendacje z lineage |
| ML | Historyczny baseline/RF jako odniesienie migracyjne | Właściwy lifecycle trzech zastosowań oraz TensorFlow challenger |
| API/UI | Obecny frontend, CRUD i projekcje wyników AI | Wersjonowane read/run API i assistant API |
| Bazy | Operacyjna PostgreSQL | Oddzielna PostgreSQL dla AI; odrębna baza/użytkownik MLflow |
| Strumień | Lokalny Redpanda, źródłowe typy zdarzeń | Własna consumer group, outbox, derived intelligence events |
| Wiedza | Zatwierdzone dokumenty źródłowe | Corpus registry, chunks, indeks, golden sets, agent traces |
| Platforma | Obecne Compose, Kustomize i AWS foundation | Compose overlay, AI Helm, Argo CD i AI-specific Terraform |

Nie tworzymy drugiego frontendu retail ani wspólnej bazy. Dane klientów nie są potrzebne agentowi ani modelom opisanym w planie. ID encji zachowujemy lub mapujemy jawnie; nie tworzymy fikcyjnego store_id, aby uzupełnić brak w API.

## Warstwy danych

1. `source_facts`: fakty potencjalnie dostępne w przedsiębiorstwie.
2. `simulation_truth`: latent demand, rzeczywisty uplift, parametry i injekcje, dostępne tylko do zatwierdzonych zastosowań ewaluacyjnych.
3. `raw_snapshot` i `curated`: niezmienne dane wejściowe i ich walidowana, wersjonowana reprezentacja w AI.
4. `features`, `labels`, `splits`: osobne produkty o opisanej semantyce czasu.
5. `predictions`, `evaluations`, `drift`, `recommendations`: wyniki AI, nie surowe targety zastępowane własnymi prognozami.

Początkowo dane przekazujemy eksportem plikowym. REST służy narzędziom i późniejszemu uzgodnionemu eksportowi, a streaming — inkrementalnym sygnałom po utwardzeniu kontraktów i trwałości. Granicę snapshot/replay określa etap 10.

## Stałe decyzje architektoniczne

| ADR | Decyzja | Konsekwencja |
|---|---|---|
| ADR-01 | Osobny serwis i repo AI | Własne API, release, baza; integracja przez kontrakty. |
| ADR-02 | PostgreSQL + pgvector | Jeden silnik dla metadata/predictions/RAG, bez dodatkowego vector DB w v1. |
| ADR-03 | Batch-first | Trening poza handlerami HTTP, utrwalone wyniki, asynchroniczne zasoby run. |
| ADR-04 | MLflow | Tracking i registry, zatwierdzenie modeli, wersjonowanie i audyt. |
| ADR-05 | GitOps w repo AI | Immutable release references i desired state w `gitops/`; bez osobnego repo konfiguracyjnego na start. |
| ADR-06 | Features point-in-time i truth separation | Brak przyszłych outcomes/ukrytej prawdy w produkcyjnych cechach. |
| ADR-07 | Read-only agent | Odczyt i propozycje do przeglądu; bez wykonywania operacyjnych zmian. |
| ADR-08 | Local-first i czasowy AWS showcase | Kosztowne zasoby tylko w określonym oknie; lokalny system pozostaje główną ścieżką rozwoju. |
| ADR-09 | Nowe wyniki AI na `retailops.intelligence.v2` | Zachowujemy legacy `.v1`; nowy grain/payload otrzymuje nowy kontrakt, projektor i jawny adapter do read models. |

W kroku 01 zapisz ADR-y w repo wraz z kontekstem, alternatywami, konsekwencjami i datą. Tabela nie jest twierdzeniem o zaakceptowanych wcześniej ADR-ach nowego repo.

ADR-09 jest nową decyzją tego skonsolidowanego planu. Nie zakłada istnienia topicu `.v2` w RetailOps. Przed publikowaniem AI wdrażamy schematy, topic init/subskrypcję, projektor, migracje i testy z etapu10. Źródłowe tematy v1 uzgadniamy z faktycznym generatorem i konsumentem. Istniejące `forecast_generated` v1 nie zmienia po cichu semantyki z wyniku produktowego za okres na wynik dzienny store/channel.

## Docelowy stack

- Python/FastAPI/Pydantic, SQLAlchemy/Alembic, jeden lockfile i CLI.
- pandas/NumPy/PyArrow/Parquet, walidatory danych, scikit-learn; TensorFlow/Keras jako challenger CPU.
- MLflow, PostgreSQL, lokalne artefakty oraz S3 w wariancie AWS.
- Bedrock chat/embedding przez adapter, pgvector, jeden LangGraph agent i wersjonowane prompty.
- Redpanda/Kafka-compatible, wersjonowane schematy, transactional outbox.
- Docker/Compose, kind, Helm, Argo CD, GitHub Actions, Terraform.
- Prometheus/Grafana, OpenTelemetry, logi JSON, Trivy/Gitleaks/audit zależności, TFLint/Checkov, kubeconform.

Konkretne wersje zależności i dostępność modeli Bedrock sprawdź przy implementacji i przypnij w lockfile/config; ten dokument nie ustanawia najnowszych wersji narzędzi.

## Docelowy układ repo AI

```text
src/retailops_ai/     # API, domena, integracje, ML, agent i RAG
pipelines/           # jobs import/features/train/evaluate/inference/drift
contracts/           # wykonywalne schematy i fixtures
tests/               # kontrakty, zachowania, błędy i integracje
data/                # tiny fixtures; wygenerowane dane poza Git
deploy/docker/       # obrazy i Compose
deploy/helm/retailops-ai/
gitops/              # Applications i środowiskowe desired state
infra/               # AI-specific Terraform modules/environments
observability/       # dashboardy, metryki, alerts
security/            # role, polityki i threat model
scripts/             # ograniczone helpery operacyjne
docs/                # ADR-y, karty, statusy i runbooki
.github/workflows/   # CI/release
```

To struktura aplikacji do zbudowania, odrębna od układu niniejszego pakietu instrukcji. Nie commituj dużych datasetów, modeli, wektorów, logów, sekretów, Terraform state ani prywatnych planów. Evidence w Git musi być małe i zanonimizowane.

## Migracja istniejącego ML

Zamroź obecne artefakty wyłącznie jako odniesienie historyczne. Obecny RF ma offline train/evaluation, a batch inference wykorzystuje moving average. Odtwórz baseline na poprawionych danych, podłącz rzeczywisty reload zatwierdzonego modelu, następnie porównuj candidate. Nie wymagaj identycznych metryk po naprawie leakage lub semantyki czasu. Zachowaj operacyjne demo; wycofuj stary kod dopiero po zastąpieniu jawnego użytkownika jego wyników.
