# ML — uruchamianie i interpretacja wyników

Kod w `ml/` tworzy lokalne cechy, prognozy i raporty. Są dwie odrębne ścieżki:
Random Forest zapisuje wytrenowany model i porównanie z baseline; pozostałe
zadania metadanych, batch inference i metryk korzystają ze średniej ruchomej.
Uruchomienie wszystkich poleceń `make ml-*` nie sprawdza jednego artefaktu
Random Forest od treningu do użycia.

Najbliższą pracę opisuje [plan poprawnej oceny ML](../plans/ml-evaluation.md).
[Otwarte ustalenia](../audits/open-findings.md) zawierają potwierdzone ograniczenia
protokołu oceny i metryk.

## Polecenia i artefakty

Polecenia wykonuje się z katalogu głównego repozytorium. Cele Make instalują
zależności API i domyślnie używają profilu `small`. Bezpośrednie moduły Python
mają domyślnie profil `demo`; przy odtwarzaniu eksperymentu podawaj profil jawnie.

| Polecenie | Co wykonuje | Główne pliki wyniku |
|---|---|---|
| `make ml-features` | Generuje dane źródłowe i agreguje cechy | `features.csv`, `feature_manifest.json` |
| `make ml-baseline` | Liczy prognozę ze średniej ruchomej | `baseline_forecasts.csv`, `model_manifest.json` |
| `make ml-trained` | Trenuje Random Forest i ocenia holdout względem baseline | `random_forest_model.joblib`, `metrics.json`, `predictions.csv`, `feature_importance.csv`, `model_metadata.json`, `model_card.md`, `experiment_inputs.json`, `experiment_source.zip`, `run_manifest.json` |
| `make ml-evaluate` | Wykonuje kroczący backtest baseline | `evaluation_report.json`, `evaluation_summary.md`, `backtest_predictions.csv` |
| `make ml-metadata` | Generuje baseline i ocenę, zapisuje lokalny rejestr | `model_metadata.json`, `model_registry.jsonl` |
| `make ml-inference` | Generuje baseline, metadane i prognozy batch | `batch_predictions.csv`, `api_forecasts.csv`, `batch_inference_manifest.json` |
| `make ml-metrics` | Uruchamia ścieżkę batch baseline i renderuje jej metryki | `model_performance.prom`, `model_performance_snapshot.json` |
| `make ml-drift` | Porównuje cechy dwóch generacji | `drift_report.json`, `drift_summary.md` |

Domyślne katalogi i parametry podaje [Makefile](../../Makefile), zmienne `ML_*`.
Wyniki większości poleceń trafiają do `data/synthetic/<profile>/`. Random Forest
zapisuje każdy przebieg osobno w
`ci-cd/reports/ml/experiments/<profile>/<run_id>/` (katalog ignorowany przez Git).
Jego katalog bazowy można zmienić przez `ML_TRAINED_OUTPUT_ROOT` w Makefile albo
`--output-root` w CLI. `--output-dir` wskazuje pojedynczy katalog i odmawia
nadpisania niepustego katalogu. CLI wypisuje faktyczną ścieżkę.
Przy wywołaniu batch/metadanych/metryk ustaw także katalogi artefaktów zależnych;
samo `--output-dir` zmienia jedynie główny wynik danego modułu.

Przykład ograniczonego eksperymentu RF:

```bash
make api-install
services/api/.venv/bin/python -m ml.models.random_forest_forecast \
  --profile small --days 90 --products 20 --stores 5 --warehouses 3 \
  --seed 42 --window-days 28 --horizon-days 7 --holdout-days 7 \
  --n-estimators 20 --random-state 42
```

To przykład wykonania obecnego protokołu, nie dopuszczenie modelu. Model
korzysta z [kontraktu cech 2.0](../reference/ml-features.md): kalendarza,
identyfikatorów serii, stałych opisów produktu i wcześniej zaobserwowanej
sprzedaży dostępnej w chwili prognozy. Nie używa zrealizowanej ceny, promocji,
stockout ani zapasu. Domyślna liczba drzew w kodzie i Makefile wynosi 80.
Wszystkie dostępne flagi sprawdzisz
przez `--help` właściwego modułu.

`experiment_inputs.json` zawiera commit i sumy plików źródłowych (wraz ze stanem
worktree), żądaną i efektywną konfigurację generatora, daty i liczności danych,
logiczne sumy tabel oraz cech, kontrakt, parametry modelu, rzeczywiste wersje
Pythona i bibliotek oraz polecenie ponowienia. `experiment_source.zip` zachowuje
dokładne bajty użytego kodu, także gdy worktree nie był zatwierdzony.
`experiment_id` zależy od tych wejść; identyczne wejścia dają ten sam
identyfikator, a każdy przebieg ma nowy `run_id`. `model_id` jest sumą SHA-256
pliku `.joblib`. Stałe `model_version=random-forest-v2` nazywa rodzinę
implementacji i samo nie identyfikuje eksperymentu. `run_manifest.json` podaje
sumy bajtowe plików i osobno logiczną
sumę prognoz. Odtwarzając wynik, użyj zapisanego środowiska i polecenia z
`experiment_inputs.json`, sprawdź sumy bajtowe artefaktów, a zgodność prognoz
oceń osobno. Identyczny hash prognoz w tym samym środowisku jest silniejszym
dowodem niż sama integralność pliku; na innym środowisku dopuszczalną tolerancję
trzeba ustalić przed eksperymentem.
[Próba identyfikacji 20/80 drzew i powtórzenia](../evidence/ml/experiment-identity-2026-09-27.md)
pokazuje zapisane identyfikatory i sumy.

## Granice obecnej implementacji

- [Kontrakt cech](../reference/ml-features.md) opisuje rzeczywisty CSV, jego
  pochodzenie i ograniczenia. Targetem jest obserwowana sprzedaż `units_sold`;
  brak wiersza nie oznacza zera ani zamknięcia sklepu.
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
- Drift porównuje liczbę wierszy, średnie kalendarzowe i udziały kategorii
  dostępnych w origin.
  Domyślne seedy 42/43 oraz progi 0,10/0,25 sprawdzają mechanizm na danych
  syntetycznych. Wynik nie jest automatycznie spięty z promocją RF.

## Dostępny artefakt modelu

Historyczny [snapshot Random Forest v1](../evidence/ml/random-forest-v1/README.md)
ma w metadanych `created_at=2026-05-13T05:22:58.789845+00:00`. Używa 20 drzew,
profilu `small` i seeda 42. Data danych treningowych nie jest datą treningu.
Zapisane metryki oraz `candidate` dotyczą tamtego przebiegu i jego ograniczonego
protokołu; nie są świeżym dowodem dopuszczalności modelu. Nowe przebiegi nie
nadpisują tego snapshotu. Bieżący kod RF ma wersję `random-forest-v2` i
osobne `experiment_id` dla różnych konfiguracji. [Próba tożsamości](../evidence/ml/experiment-identity-2026-09-27.md)
została wykonana jeszcze z cechami 1.0; jej wyniki nie mierzą wpływu obecnej
poprawki. Warianty 20 i 80 drzew mają osobne `experiment_id`;
ich metryk nie należy przedstawiać jako skutku jednej zmiany bez kontrolowanego
porównania. Aktualny raport ma `evaluation_scope=legacy_rolling_holdout_exploratory_only`.

## Sprawdzenie zmian

Testy zachowań są w `services/api/tests/test_demand_feature_generation.py`,
`test_random_forest_forecasting_model.py`, `test_baseline_forecasting_model.py`,
`test_baseline_evaluation_report.py`, `test_model_metadata_registry.py`,
`test_batch_forecast_inference.py`, `test_model_performance_metrics.py`
i `test_demand_feature_drift.py`. Uruchamiaj testy właściwe dla zmiany według
[instrukcji testowania](testing.md). Samo przejście obecnych testów nie zamyka
otwartych ustaleń metodologicznych.
