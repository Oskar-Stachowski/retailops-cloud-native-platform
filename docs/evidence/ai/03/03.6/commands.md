# Polecenia odbioru AI 03.6

To zapis wykonania; przenośną instrukcję zawiera [runbook](../../../../reference/ai03-cross-repo.md).

```sh
# Wykonane polecenia odbioru 29.09.2026; zależności zainstalowane przed pomiarem.
# RetailOps, czysty ai/03-01-parquet na 25fb0b887503c119055af86b63991299465096b9:
services/api/.venv/bin/python scripts/data/verify_ai03_cross_repo.py --consumer-root /private/tmp/retailops-ai-03-04 --consumer-python /private/tmp/retailops-ai-03-04/.venv/bin/python --producer-revision 25fb0b887503c119055af86b63991299465096b9 --consumer-revision cb053cc29c1906d79108cba2c70f88b56e454211
# Wynik: passed, 6 pełnych przebiegów. Po zakończeniu consumer otrzymał wyłącznie docs do 7dd00cc.

# Izolowany worktree AI, PYTHONPATH=src; interpreter z worktree AI 03:
env PYTHONPATH=src /private/tmp/retailops-ai-03-04/.venv/bin/python -m pytest -q tests/test_source_snapshot_import.py -k null_temporal_columns_and_empty_tables_keep_zero_ranges
# 4 passed, 48 deselected; 0.70 s.
/private/tmp/retailops-ai-03-04/.venv/bin/ruff check src/retailops_ai/source_snapshot/canonical.py src/retailops_ai/source_snapshot/tables.py tests/test_source_snapshot_import.py
/private/tmp/retailops-ai-03-04/.venv/bin/ruff format --check src/retailops_ai/source_snapshot/canonical.py src/retailops_ai/source_snapshot/tables.py tests/test_source_snapshot_import.py
env PYTHONPATH=src /private/tmp/retailops-ai-03-04/.venv/bin/mypy --strict src/retailops_ai/source_snapshot/canonical.py src/retailops_ai/source_snapshot/tables.py
env PYTHONPATH=src /private/tmp/retailops-ai-03-04/.venv/bin/python scripts/check_repository.py
# Wszystkie kontrole passed. Pełną regresję 747 testów wykonał Required CI AI.

# Zdalne Required CI, dokładne workflow/steps/jobs w verification.json i linkach README.
# RetailOps: make data-generate data-quality data-contracts data-scenario-report DATA_PROFILE=small
# RetailOps: make data-parquet-check (89 testów + oba pełne profile z re-exportem dwukrotnie)
# RetailOps: ta sama komenda cross-repo, producer 9d75f9f8a114f2baa3923fd15cb6b03b94431b8c
#            (GitHub PR merge checkout), consumer cb053cc29c1906d79108cba2c70f88b56e454211.
# Repo AI: make bootstrap check (747 testów, lint/mypy/docs/kontrakty/handoff/import/curated/package/config)
# Repo AI, osobny job: make bootstrap compose-smoke (rzeczywisty Compose/persistence).
```
