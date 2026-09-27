# Reprodukcje audytu przygotowań AI

Dotyczą rewizji i środowisk z [raportu 27.09.2026](2026-09-27-readiness.md).
Polecenia wykonuje się z root repo. Przykładowy URL zawiera wyłącznie fikcyjne
dane; pierwsze dwa przypadki działają w pamięci, bez bazy i zapisu datasetu.

## OPS-04: wybór bazy po zmianie ścieżki URL

```bash
PYTHONDONTWRITEBYTECODE=1 services/api/.venv/bin/python - <<'PY'
from urllib.parse import urlsplit, urlunsplit
from psycopg.conninfo import conninfo_to_dict
from sqlalchemy.dialects.postgresql.psycopg import PGDialect_psycopg
from sqlalchemy.engine import make_url

source = "postgresql://demo:placeholder@127.0.0.1/retailops?dbname=retailops"
isolated = urlunsplit(urlsplit(source)._replace(path="/retailops_seed_test_probe"))
print("URI path:", urlsplit(isolated).path)
print("psycopg dbname:", conninfo_to_dict(isolated)["dbname"])
_, params = PGDialect_psycopg().create_connect_args(make_url(isolated))
print("SQLAlchemy psycopg dialect dbname:", params["dbname"])
PY
```

Wynik: ścieżka `/retailops_seed_test_probe`, ale obydwa sterowniki wybierają
`retailops`. Nie wykonano połączenia ani `TRUNCATE`.

## ML-07: zmiana historii po dodaniu późniejszego zdarzenia

```bash
PYTHONPATH=. services/api/.venv/bin/python - <<'PY'
from datetime import date, timedelta
from data.generator.main import DatasetGenerationConfig, build_dataset
from ml.features.demand_forecast import build_demand_feature_rows
from ml.models.random_forest_forecast import build_training_features

config = DatasetGenerationConfig(profile="demo")
tables = build_dataset(config)
sale = dict(tables["sales"][0])
tables["sales"] = [sale]
before = build_demand_feature_rows(tables, config)[0]
origin = date.fromisoformat(before["date"]) + timedelta(days=1)
target = {**before, "date": origin.isoformat()}
features_before = build_training_features(
    target, [before], window_days=7, origin=origin
)
tables["sales"].append({
    **sale, "id": "late-probe", "ingested_at": "2099-01-01T00:00:00+00:00"
})
after = build_demand_feature_rows(tables, config)[0]
features_after = build_training_features(
    target, [after], window_days=7, origin=origin
)
print("origin", origin)
print("availability", before["observation_available_at"],
      "->", after["observation_available_at"])
print({key: (features_before[key], features_after[key])
       for key in features_before if features_before[key] != features_after[key]})
PY
```

Wynik: parametr origin `2026-05-01`, dostępność agregatu przesuwa się z
`2026-04-30T08:00:00+00:00` do `2099-01-01T00:00:00+00:00`.
`lag_1_units` i `rolling_mean_units` zmieniają się z 3 na 0,
`lag_1_available` i `training_observation_count` z 1 na 0. Jest to
celowo zmodyfikowany input funkcji, nie zmiana ani opis zapisanej kampanii RF.

## Integralność i ponowny odczyt zapisanych RF80

Sprawdzenie 12 sum kontrolnych małego evidence, bez zależności ML:

```bash
python3 - <<'PY'
from hashlib import sha256
from pathlib import Path

root = Path("docs/evidence/ml/fixed-origin-rf-2026-09-27")
lines = (root / "checksums.sha256").read_text().splitlines()
for line in lines:
    expected, name = line.split(maxsplit=1)
    assert sha256((root / name).read_bytes()).hexdigest() == expected, name
print("verified evidence files:", len(lines))
PY
```

Odczyt zaufanych, lokalnych modeli wymaga zachowanych surowych artefaktów
z kampanii oraz jej wersji bibliotek, opisanych w [raporcie RF](../ml/fixed-origin-rf-2026-09-27/README.md).
Poniżej interpreter zachowanego venv eksperymentu; jego ścieżka jest lokalna.
Na innym komputerze odtwórz środowisko i kampanię zgodnie z raportem RF.

```bash
PYTHONPATH=. /private/tmp/retailops-ml-acceptance-20260927/bin/python - <<'PY'
from pathlib import Path
from ml.experiments.assessed_run import load_assessed_run

root = Path("ci-cd/reports/ml/experiments/small")
for run_id in ("4d88f7e8e1334360afc0d662b1375b68", "fa1ca9c081db41e1b2d5788d757b7272"):
    run = load_assessed_run(root / run_id)
    late_days = sum(str(row["observation_available_at"])[:10] > str(row["date"])[:10]
                    for row in run.panel)
    print(run_id, len(run.panel), len(run.predictions),
          run.metrics["model_status"], run.manifest["model_id"], late_days)
PY
```

Każdy odczyt weryfikuje 9 surowych artefaktów oraz odtwarza prognozy.
W obu przypadkach: 9000 wierszy panelu, 2800 prognoz, `rejected`, zero
obserwacji z dostępnością późniejszego dnia i SHA modelu
`571d1b303e2fe1c11b31ea88b79c100d1e6497d3447cd2e995435192a60667ab`.
