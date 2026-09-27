# Audyt przygotowań do AI 00 — 27.09.2026

**Decyzja: można rozpocząć instrukcję AI 00. Nie wszystkie przygotowania są
w pełni zamknięte i nie ma jeszcze zgody na serving ani odbioru dalszych etapów.**
Najbliższa poprawka to OPS-04: parametr połączenia `dbname` może ominąć
izolację bazy testu seeda. Audyt AI 00 można prowadzić bez uruchamiania tego
testu na serwerze z wartościowymi danymi.

## Rewizja, zakres i dowody

Badano `prep/before-ai-00` na
`4da25cba4acd721ce88cb5c07ac7bec23cc8f0f4`, przy czystym worktree. Odczyt
GitHub z 2026-09-27 UTC potwierdził ten sam SHA na `origin/main` i
`origin/prep/before-ai-00`. Porównanie objęło historię przygotowań od
`35b5586`, pierwotne siedem kroków ML i cztery pilne zadania OPS, aktualny
kod oraz instrukcje AI 00–17. Zależności 18 instrukcji zgadzają się z
`etapy.json` i nie tworzą cyklu.

W tym audycie wykonano **103 ukierunkowane testy lokalne**, sprawdzenie
konfiguracji Compose, integralności zapisanych artefaktów oraz dwie
reprodukcje w pamięci. Środowisko testów: macOS arm64, CPython 3.11.15,
pytest 9.0.3; lokalny venv API używa scikit-learn 1.5.2, joblib 1.4.2,
NumPy 2.4.4 i SciPy 1.17.1. Odczyt modeli wykonano oddzielnie w zachowanym
venv eksperymentu, ze scikit-learn 1.9.1; nie przypisujemy mu 103 testów.

PR-y [53](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/pull/53),
[54](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/pull/54),
[55](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/pull/55),
[56](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/pull/56)
i [57](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/pull/57)
są scalone. Każdy ma `required-result=success`; końcowy merge `4da25cb`
także ma [zielone Required CI](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/actions/runs/36326933047/job/108642705854).
Nie znaleziono otwartych PR-ów. Ochrona `main` wymaga PR i `required-result`,
ma strict checks oraz obejmuje administratorów. Mały zapis odczytu:
[github-verification.json](github-verification.json).

To odczyt wykonanych workflow, nie nowy lokalny test runtime. Nie uruchamiano
seeda, migracji ani zapisu do rzeczywistej bazy, nowego stosu Docker,
Kubernetes lub AWS. Nie wykonywano ponownego treningu kampanii RF ani całej
instrukcji AI 00. Jej podwójna generacja małego zestawu, pełny audyt generatora,
kontraktów i backlog pozostają do wykonania.

## Co potwierdzają przygotowania

| Zakres | Obecne zachowanie i dowód |
|---|---|
| Tożsamość eksperymentu | Manifesty wiążą kod, konfigurację, zależności, dane, model i prognozy. Zweryfikowano 12 sum plików evidence oraz po 9 surowych artefaktów RF80 i powtórzenia. |
| Cechy i ocena czasowa | Kalendarzowe lagi, jawne zero/brak, jeden origin dla całego horyzontu, trzy okna walidacyjne i odłożony test. RF i baseline mają te same oceniane rekordy. Niepewne inventory, ceny, promocje i stockout są wyłączone z cech. Zakres obejmuje kompletny profil syntetyczny, nie dowolne źródło historyczne. |
| Metryki i dopuszczenie | Nieokreślone WAPE/MAPE nie stają się zerem. Wersjonowana polityka weryfikuje komplet warunków i blokuje ręczne nadanie statusu w ścieżce ocenionego RF. |
| Artefakt i odtworzenie | Batch, metadata i metryki odczytują ten sam oceniony RF. Ponowny `load_assessed_run()` dla obu zapisanych przebiegów potwierdził 9000 wierszy panelu, 2800 prognoz i identyczny SHA modelu. |
| Wynik eksperymentu | RF80 ma WAPE 159,8564% wobec 148,1966% średniej ruchomej i status `rejected`. To poprawny wynik przygotowań, bez kwalifikacji do serving. Szczegóły: [ocena RF](../ml/fixed-origin-rf-2026-09-27/README.md). |
| Trwałość i lokalny dostęp | Zwykły `compose-down` zachowuje wolumeny; seed jest osobnym profilem. Sprawdzono konfigurację podstawową i nakładkę observability: siedem publikowanych portów pozostaje na `127.0.0.1`, również przy próbie nadpisania `HOST_BIND`. |
| Diagnostyka testów DB | Trzy testy preflight potwierdzają stałe komunikaty bez sekretów w terminalu i JUnit, dla skip oraz fail. To zakres diagnostyki Pytest, nie globalny filtr wyjątków aplikacji. |

## Otwarte problemy i kolejność dalszych prac

Aktualne kryteria zamknięcia są wyłącznie w
[otwartych ustaleniach](../../audits/open-findings.md).

1. **OPS-04, P1 — niepełna izolacja seeda.** Fixture zmienia ścieżkę URI,
   zachowując query `dbname`. Psycopg oraz SQLAlchemy wybierają przez to bazę
   źródłową. Seed zawiera `TRUNCATE`. Poprawić przed poleganiem na izolacji
   testów na serwerze z wartościowymi danymi. Reprodukcja poniżej nie otwiera
   połączeń; nie stwierdzono utraty danych podczas audytu.
2. **ML-07, P2 — brak wersji dziennych agregatów.** Dodanie późniejszej
   sprzedaży historycznego dnia przesuwa dostępność całej sumy i zmienia
   wcześniejsze cechy. To konkretny warunek odbioru AI 02–04. Aktualny
   syntetyczny generator opóźnia zdarzenia najwyżej do 21:00 tego samego dnia,
   a zapisany panel RF ma zero obserwacji dostępnych dopiero następnego dnia.
   Ustalenie nie unieważnia tej oceny RF i nie blokuje AI 00.
3. **OPS-03 i OPS-07** pozostają warunkami odbioru streamingu w AI 10:
   trwałość ACK/DLQ oraz zgodność kontraktu, generatora i consumera.
4. **OPS-06** pozostaje warunkiem odtwarzalnych wydań: przypięte actions
   i obrazy. W nowym repo stosować od AI 01; istniejące ścieżki uporządkować
   przed wydaniami i wdrożeniami AI 14–15.

Podczas audytu poprawiono w instrukcjach architektury i AI 04 nieaktualne
stwierdzenie, że obecny batch używa średniej ruchomej, oraz uściślono przykład
historycznej odpowiedzi RAG w AI 11. Obecny batch jest diagnostycznym batchem
RF. Instrukcja testów opisuje ograniczenie OPS-04, a kontrakt cech — ML-07.

## Co oznacza zgoda na rozpoczęcie AI

| Przejście | Wymagany wynik |
|---|---|
| AI 00 | Można rozpocząć teraz. Zapisać audyt aktualnego SHA, pomiary generatora i backlog. Niniejszy raport jest wejściem do etapu, nie jego odbiorem. |
| AI 01–03 | Odrębne repo, zależności, CI i podstawowe auth od 01, źródłowe bramki 02, wersjonowany eksport/import i curated w 03. Tożsamości danych muszą zależeć od treści, nie tylko profilu/dat/seeda lub lokalnej ścieżki interpretera. Pierwszy snapshot nie wymaga brokera, AWS ani działającej DB RetailOps. |
| AI 04–05 | Nowa ocena na zwalidowanym snapshotcie, historyczne wersje/as-of, wspólne baseline’y i modele, zamrożony holdout i polityka. Tracking zachowuje także nieudane i odrzucone przebiegi; dopiero zakwalifikowany model lub baseline może być promowany do aktywnego serving. Worker, API i rollback wymagają osobnego odbioru. Obecny odrzucony RF nie jest championem. |
| AI 06–09 | Ledger oraz bramki danych dla stockout/anomaly. Po zmianach symulatora nowy eksport/import i ponowna ocena; wcześniejszy forecast-only snapshot nie dowodzi gotowości tych zastosowań. |
| AI 10–12 | Kontrakty integracji, trwałe przetwarzanie i rzeczywista weryfikacja tożsamości/uprawnień. Lokalne demo `user_id` i loopback nie zastępują auth dla usług AI, narzędzi agenta ani dostępu innych użytkowników. |
| AI 13–17 | Własne bramki monitoringu, obrazów, release, infrastruktury, kosztów i bezpieczeństwa; wcześniejsze przygotowania nie oznaczają wdrożenia AWS/EKS ani odbioru produkcyjnego. |

## Polecenia wykonanych kontroli

W katalogu głównym repo, 87 testów ML (`87 passed in 3.50s`):

```bash
PYTHONPATH=services/api:. services/api/.venv/bin/python -m pytest -q \
  services/api/tests/test_fixed_origin_evaluation.py \
  services/api/tests/test_demand_feature_generation.py \
  services/api/tests/test_forecast_metrics.py \
  services/api/tests/test_forecast_admission_policy.py \
  services/api/tests/test_random_forest_forecasting_model.py \
  services/api/tests/test_assessed_rf_pipeline.py \
  services/api/tests/test_batch_forecast_inference.py \
  services/api/tests/test_model_performance_metrics.py \
  services/api/tests/test_model_metadata_registry.py \
  services/api/tests/test_baseline_evaluation_report.py \
  services/api/tests/test_baseline_forecasting_model.py \
  services/api/tests/test_ml_feature_dataset_contract.py
```

16 testów operacyjnych (`16 passed in 4.11s`) i walidacja Compose:

```bash
env -u DATABASE_URL PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=services/api:. \
  services/api/.venv/bin/python -m pytest \
  services/api/tests/test_db_availability_diagnostics.py \
  services/api/tests/test_seed_data_profiles.py \
  services/api/tests/test_realtime_consumer_runner.py \
  services/api/tests/test_demo_auth_boundary_readiness.py \
  -q -p no:cacheprovider
COMPOSE='docker compose --env-file /dev/null' \
  python3 scripts/ci/check_compose_local_boundary.py
```

Zielony test consumera potwierdza obecne zachowanie, także commit po błędnym
JSON; nie jest dowodem zamknięcia OPS-03. Pełne testy seeda z DB nie były tu
uruchamiane. Reprodukcje OPS-04 i ML-07 wraz z poleceniami weryfikacji
artefaktów: [reproductions.md](reproductions.md).
