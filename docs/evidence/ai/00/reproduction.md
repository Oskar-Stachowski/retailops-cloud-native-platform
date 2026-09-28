# Odtworzenie pomiarów AI 00

Komendy zakładają root RetailOps na rewizji wskazanej w [raporcie](README.md).
Do generatora, skryptów i testów użyto `services/api/.venv/bin/python`;
wersje są w [execution.json](execution.json). Środowiska nie instalowano ponownie.
Nowe środowisko może rozwiązać inne nieprzypięte zależności przechodnie.

## Generator i kontrakty

W audycie katalog roboczy to `/private/tmp/retailops-ai-00-vcp9wzdx`.
Przy odtwarzaniu utwórz nowy; nie kieruj outputu do `data/demo` ani fixtures.

```bash
audit_dir=$(mktemp -d /private/tmp/retailops-ai-00.XXXXXX)
services/api/.venv/bin/python -m data.generator.main \
  --profile small --seed 42 --output-dir "$audit_dir/small-a"
services/api/.venv/bin/python -m data.generator.main \
  --profile small --seed 42 --output-dir "$audit_dir/small-b"
services/api/.venv/bin/python -m data.generator.main \
  --profile small --seed 42 --products 20 --output-dir "$audit_dir/small-20"
PYTHONPATH=. services/api/.venv/bin/python scripts/data/audit_ai00_source.py \
  --first "$audit_dir/small-a" --repeat "$audit_dir/small-b" \
  --contrast "$audit_dir/small-20" --output "$audit_dir/source-measurements.json"
env -u DATABASE_URL PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=services/api:. \
  services/api/.venv/bin/python scripts/ci/audit_ai00_contracts.py \
  --first "$audit_dir/small-a" --contrast "$audit_dir/small-20" \
  --output "$audit_dir/contracts.json"
```

Skrypty są sondami bazowego `small/seed42`, nie docelową bramką AI 02.
Zapisują także niepoprawne zachowania z raportu; samo exit 0 nie oznacza gotowości AI.
Nie modyfikują runtime, nie publikują zdarzeń i nie łączą się z DB/brokerem.
Przy zmianie schematu źródła należy dostosować sondy, zachowując znaczenie kontroli.

## Testy

Wynik: **138 passed in 4.87s**, bez skip/error/failure. Surowy JUnit:
`ci-cd/reports/ai-00/focused-tests.xml` (ignorowany); jego hash i lista modułów
są w execution.json. To testy lokalne, nie pełny runtime.

```bash
env -u DATABASE_URL PYTHONDONTWRITEBYTECODE=1 services/api/.venv/bin/python -m pytest -q \
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
  services/api/tests/test_ml_feature_dataset_contract.py \
  services/api/tests/test_data_generator_cli.py \
  services/api/tests/test_data_contracts.py \
  services/api/tests/test_realtime_consumer.py \
  services/api/tests/test_realtime_consumer_runner.py \
  services/api/tests/test_api_list_contract_readiness.py \
  services/api/tests/test_demo_auth_boundary_readiness.py \
  --junitxml=ci-cd/reports/ai-00/focused-tests.xml
services/api/.venv/bin/python -m ruff check --select E,F,I \
  scripts/data/audit_ai00_source.py scripts/ci/audit_ai00_contracts.py
services/api/.venv/bin/python -m ruff format --check \
  scripts/data/audit_ai00_source.py scripts/ci/audit_ai00_contracts.py
```

## Odczyt zachowanych RF

Wymaga **lokalnych, zaufanych** artefaktów opisanych w
[ocenie RF](../../ml/fixed-origin-rf-2026-09-27/README.md). Nie są częścią checkoutu.
Użyty interpreter: `/private/tmp/retailops-ml-acceptance-20260927/bin/python`,
scikit-learn 1.9.1/joblib 1.6.0/NumPy 2.4.6/SciPy 1.17.1.
Rdzeń wykonanej weryfikacji, bez nowego treningu ani zapisu batchu:

```bash
PYTHONPATH=. /private/tmp/retailops-ml-acceptance-20260927/bin/python - <<'PY'
import hashlib
import json
from pathlib import Path
from ml.experiments.assessed_run import load_assessed_run
from ml.inference.batch_forecast import build_batch_predictions

evidence = Path('docs/evidence/ml/fixed-origin-rf-2026-09-27')
for line in (evidence / 'checksums.sha256').read_text().splitlines():
    checksum, name = line.split(maxsplit=1)
    assert hashlib.sha256((evidence / name).read_bytes()).hexdigest() == checksum
for run_id in ('4d88f7e8e1334360afc0d662b1375b68', 'fa1ca9c081db41e1b2d5788d757b7272'):
    run = load_assessed_run(Path('ci-cd/reports/ml/experiments/small') / run_id)
    assert run.metrics['model_status'] == 'rejected'
    assert len(run.panel) == 9000 and len(run.predictions) == 2800
    if run_id.startswith('4d88'):
        rows = build_batch_predictions(run)
        saved = json.loads((evidence / 'rf-80-batch-manifest.json').read_text())
        assert len(rows) == 700
        assert all(all(row[k] == saved[k] for k in ('model_id', 'run_id', 'experiment_id'))
                   for row in rows)
    print(run_id, run.metrics['model_id'], run.metrics['model_status'])
PY
```

GitHub odczytano przez REST: refs `main` i `ai/implementation`, otwarte PR-y,
PR 58 i check-runs źródłowego SHA; zapis to [github.json](github.json).
Nie wysłano zmian ani nie uruchomiono workflow. Nowy odczyt może mieć inny wynik.
