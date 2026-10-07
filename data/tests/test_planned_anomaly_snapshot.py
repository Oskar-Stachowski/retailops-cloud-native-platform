"""Real combined anomaly/known-plan export retains older schema bytes and truth isolation."""

import json
import tempfile
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest

from data.anomalies.example import example_plan
from data.anomalies.physical_scenarios import physical_example_plan
from data.anomalies.source_process import build_tables
from data.export.inventory_snapshot import export_inventory_snapshot, verify_inventory_snapshot
from data.export.policy import GENERATED_ROOT
from data.generator.configuration import DatasetGenerationConfig
from data.inventory.qualification_io import write_qualification
from data.inventory.run_source_dataset import default_inventory_config
from data.inventory.source_dataset_io import write_source_dataset


@pytest.mark.parametrize("kind", ["demand", "physical"])
def test_native_planned_anomaly_export_matches_exact_extended_schemas(kind):
    generation = DatasetGenerationConfig(
        profile="ai-smoke", days=30, products=8, stores=3, warehouses=2,
        seed=42, forecast_plan_days=14,
    )
    plan = (example_plan if kind == "demand" else physical_example_plan)(generation)
    config = default_inventory_config(generation)
    GENERATED_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="planned-anomaly-test-", dir=GENERATED_ROOT) as temporary:
        root = Path(temporary)
        tables, context = build_tables(generation, plan, config)
        source = write_source_dataset(tables, context, generation, config, root / "raw", scenario_plan=plan)
        qualification = write_qualification(source, root / "qualification")
        result = export_inventory_snapshot(
            source, source.name, qualification, root / "snapshots",
            required_use_cases=("forecast_source", "inventory_source", "anomaly_source"),
        )
        destination = Path(result["path"])
        manifest = verify_inventory_snapshot(destination)
        assert manifest["schema_version"] == "1.2.0"
        assert manifest["source"]["descriptor"]["generator_version"] == "1.0.0"
        assert manifest["source"]["descriptor"]["resolved_parameters"]["forecast_plan_days"] == 14
        for name, extended in [
            ("anomaly_snapshot.v1_2.schema.json", "anomaly_snapshot.v1_2.forecast.schema.json"),
            ("anomaly_source_dataset.v2_8.schema.json", "anomaly_source_dataset.v2_8.forecast.schema.json"),
        ]:
            raw = (destination / "schemas" / name).read_bytes()
            assert raw == (Path("data/contracts") / extended).read_bytes()
        Draft202012Validator(json.loads((destination / "schemas/anomaly_snapshot.v1_2.schema.json").read_bytes())).validate(manifest)
        assert not (destination / "evaluation_truth").exists()
