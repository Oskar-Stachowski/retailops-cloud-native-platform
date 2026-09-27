# ML — uruchamianie i interpretacja wyników

Kod w `ml/` tworzy lokalne cechy, prognozy i raporty. Są dwie odrębne ścieżki:
Random Forest zapisuje wytrenowany model i porównanie z baseline; pozostałe
zadania metadanych, batch inference i metryk korzystają ze średniej ruchomej.
Uruchomienie wszystkich poleceń `make ml-*` nie sprawdza jednego artefaktu
Random Forest od treningu do użycia.

Najbliższą pracę opisuje [plan poprawnej oceny ML](../plans/ml-evaluation.md).
[Otwarte ustalenia](../audits/open-findings.md) zawierają potwierdzone ograniczenia
czasu cech, protokołu oceny, metryk i tożsamości danych.

## Polecenia i artefakty

Polecenia wykonuje się z katalogu głównego repozytorium. Cele Make instalują
zależności API i domyślnie używają profilu `small`. Bezpośrednie moduły Python
mają domyślnie profil `demo`; przy odtwarzaniu eksperymentu podawaj profil jawnie.

| Polecenie | Co wykonuje | Główne pliki wyniku |
|---|---|---|
| `make ml-features` | Generuje dane źródłowe i agreguje cechy | `features.csv`, `feature_manifest.json` |
| `make ml-baseline` | Liczy prognozę ze średniej ruchomej | `baseline_forecasts.csv`, `model_manifest.json` |
| `make ml-trained` | Trenuje Random Forest i ocenia holdout względem baseline | `random_forest_model.joblib`, `metrics.json`, `predictions.csv`, `feature_importance.csv`, `model_metadata.json`, `model_card.md` |
| `make ml-evaluate` | Wykonuje kroczący backtest baseline | `evaluation_report.json`, `evaluation_summary.md`, `backtest_predictions.csv` |
| `make ml-metadata` | Generuje baseline i ocenę, zapisuje lokalny rejestr | `model_metadata.json`, `model_registry.jsonl` |
| `make ml-inference` | Generuje baseline, metadane i prognozy batch | `batch_predictions.csv`, `api_forecasts.csv`, `batch_inference_manifest.json` |
| `make ml-metrics` | Uruchamia ścieżkę batch baseline i renderuje jej metryki | `model_performance.prom`, `model_performance_snapshot.json` |
| `make ml-drift` | Porównuje cechy dwóch generacji | `drift_report.json`, `drift_summary.md` |

Domyślne katalogi i parametry podaje [Makefile](../../Makefile), zmienne `ML_*`.
Wyniki trafiają do podkatalogów `data/synthetic/<profile>/`. `small` jest objęty
wyjątkiem w `.gitignore`, więc nowe pliki w nim nie są automatycznie ignorowane.
Do eksperymentów używaj osobnego katalogu wynikowego i sprawdzaj `git status`.
Przy wywołaniu batch/metadanych/metryk ustaw także katalogi artefaktów zależnych;
samo `--output-dir` zmienia jedynie główny wynik danego modułu.

Przykład ograniczonego eksperymentu RF, z własnym katalogiem wyników:

```bash
make api-install
ml_run_dir=$(mktemp -d /tmp/retailops-ml.XXXXXX)
services/api/.venv/bin/python -m ml.models.random_forest_forecast \
  --profile small --days 90 --products 20 --stores 5 --warehouses 3 \
  --seed 42 --window-days 28 --holdout-days 7 --n-estimators 20 \
  --output-dir "$ml_run_dir"
```

To przykład wykonania obecnego protokołu, nie dopuszczenie modelu. Domyślna
liczba drzew w kodzie i Makefile wynosi 80. Wszystkie dostępne flagi sprawdzisz
przez `--help` właściwego modułu.

## Granice obecnej implementacji

- [Kontrakt cech](../reference/ml-features.md) opisuje rzeczywisty CSV, jego
  pochodzenie i ograniczenia. Targetem jest obserwowana sprzedaż `units_sold`.
- Status RF `candidate` wynika wyłącznie z niższego WAPE od baseline.
  Nie stanowi pełnej polityki dopuszczenia ani dowodu poprawności czasowej.
- Status rejestru baseline jest parametrem CLI. `approved` jest dozwoloną
  wartością tekstową, a nie wynikiem wdrożonego procesu zatwierdzania.
- `api_forecasts.csv` jest plikiem zgodnym kształtem z rekordami prognoz API.
  Moduł batch nie zapisuje go automatycznie do PostgreSQL. Dane prognoz seed/API
  i artefakt zapisany przez batch mają osobne ścieżki zasilania.
- Pole `confidence_level` w eksporcie batch jest heurystyką liczby obserwacji,
  nie skalibrowanym prawdopodobieństwem ani przedziałem predykcji.
- Plik `.prom` nie oznacza zbierania tych metryk przez działający Prometheus.
  Reguły modeli są w `observability/prometheus/rules/model-alerts.yml`;
  odbiór wymaga potwierdzenia rzeczywistego źródła próbek.
- Drift porównuje liczbę wierszy, średnie numeryczne i udziały kategorii.
  Domyślne seedy 42/43 oraz progi 0,10/0,25 sprawdzają mechanizm na danych
  syntetycznych. Wynik nie jest automatycznie spięty z promocją RF.

## Dostępny artefakt modelu

Najnowszy zachowany [snapshot Random Forest v1](../evidence/ml/random-forest-v1/README.md)
ma w metadanych `created_at=2026-05-13T05:22:58.789845+00:00`. Używa 20 drzew,
profilu `small` i seeda 42. Data danych treningowych nie jest datą treningu.
Zapisane metryki oraz `candidate` dotyczą tamtego przebiegu i jego ograniczonego
protokołu; nie są świeżym dowodem dopuszczalności modelu. Kolejny eksperyment
powinien mieć nową tożsamość i pozostawić ten artefakt bez nadpisania.

## Sprawdzenie zmian

Testy zachowań są w `services/api/tests/test_demand_feature_generation.py`,
`test_random_forest_forecasting_model.py`, `test_baseline_forecasting_model.py`,
`test_baseline_evaluation_report.py`, `test_model_metadata_registry.py`,
`test_batch_forecast_inference.py`, `test_model_performance_metrics.py`
i `test_demand_feature_drift.py`. Uruchamiaj testy właściwe dla zmiany według
[instrukcji testowania](testing.md). Samo przejście obecnych testów nie zamyka
otwartych ustaleń metodologicznych.
